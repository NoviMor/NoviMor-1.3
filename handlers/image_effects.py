import asyncio
import logging
import os
import pathlib

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import ContextTypes

from add_image_effects import ImageEffectsEngine
from state_machine import States
from handlers.common import is_video_file, cancel

async def ask_image_effects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to select image effects."""
    if 'selected_image_effects' not in context.user_data:
        context.user_data['selected_image_effects'] = []
    return await _return_to_image_effects_menu(update, context)

async def _return_to_image_effects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main image effects menu and current selections."""
    engine = ImageEffectsEngine()
    effects_list = list(engine.effects_map.keys())
    
    keyboard = [effects_list[i:i + 3] for i in range(0, len(effects_list), 3)]
    keyboard.append(['✅ Done Selecting', '🔄 Reset', '❌ Cancel'])
    
    selected = context.user_data.get('selected_image_effects', [])
    
    if not selected:
        effect_text = "Current image effects: None."
    else:
        effect_lines = []
        for i, eff in enumerate(selected):
            if isinstance(eff, tuple):
                name = f"{eff[0]} ({eff[1].capitalize()})"
                if eff[0] == 'look-up table':
                    name = f"{eff[0]} ({os.path.basename(eff[1])})"
                effect_lines.append(f"{i+1}. {name}")
            else:
                effect_lines.append(f"{i+1}. {eff}")
        effect_text = "Current image effects:\n" + "\n".join(effect_lines)

    await update.message.reply_text(
        f"{effect_text}\n\n"
        "Select an effect, click an existing one to remove it, or press 'Done Selecting'.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return States.CHOOSE_IMAGE_EFFECTS

async def choose_image_effects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user's selection of image effects, branching to sub-conversations."""
    choice = update.message.text
    if choice == '❌ Cancel':
        return await cancel(update, context)

    if choice == '🔄 Reset':
        context.user_data['selected_image_effects'] = []
        return await _return_to_image_effects_menu(update, context)
        
    selected = context.user_data.get('selected_image_effects', [])

    if 'Done' in choice:
        if not selected:
            await update.message.reply_text("No effects selected. Returning to caption input.", reply_markup=ReplyKeyboardRemove())
            return States.CAPTION
        else:
            effects_to_apply_names = [eff[0] if isinstance(eff, tuple) else eff for eff in selected]
            await update.message.reply_text(f"Applying effects: {', '.join(effects_to_apply_names)}. Please wait...", reply_markup=ReplyKeyboardRemove())
            return await process_and_confirm_image_effects(update, context)

    if choice == 'look-up table' and any(isinstance(eff, tuple) and eff[0] == 'look-up table' for eff in selected):
        context.user_data['selected_image_effects'] = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
        await update.message.reply_text("Previous LUT removed. Please select a new one.")

    parameterized_effects = {
        'look-up table': (States.ASK_IMAGE_LUT_TYPE, [['📁 Built-in', '📤 Upload Custom']]),
        'Color Saturation': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Contrast / Brightness': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Chromatic Aberration': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Pixelated Effect': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Film Grain': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Glitch': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Neon Glow': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Cartoon / Painterly': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Vignette': (States.ASK_IMAGE_EFFECT_LEVEL, [['Low', 'Medium', 'High']]),
        'Rotate': (States.ASK_IMAGE_EFFECT_LEVEL, [['15°', '45°', '90°']])
    }

    if choice in parameterized_effects:
        state, options = parameterized_effects[choice]
        context.user_data['current_effect_choice'] = choice
        keyboard = options + [['❌ Cancel']]
        await update.message.reply_text(f"Please choose an option for {choice}:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return state

    if any(eff == choice or (isinstance(eff, tuple) and eff[0] == choice) for eff in selected):
        selected = [eff for eff in selected if not (eff == choice or (isinstance(eff, tuple) and eff[0] == choice))]
    elif len(selected) < 3:
        selected.append(choice)
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_IMAGE_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You can only select up to 3 effects for images.")

    context.user_data['selected_image_effects'] = selected
    return await _return_to_image_effects_menu(update, context)

async def set_image_effect_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    effect_name = context.user_data.get('current_effect_choice')
    level_map = {'low': 'low', 'medium': 'medium', 'high': 'high', '15°': 'low', '45°': 'medium', '90°': 'high'}
    level = level_map.get(choice.lower())

    if not level or not effect_name:
        await update.message.reply_text("An error occurred. Returning to menu.")
        return await _return_to_image_effects_menu(update, context)

    selected = context.user_data.get('selected_image_effects', [])
    selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == effect_name)]
    if len(selected) < 3:
        selected.append((effect_name, level))
        context.user_data['selected_image_effects'] = selected
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_IMAGE_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You already have 3 effects. Remove one to add another.")

    if 'current_effect_choice' in context.user_data:
        del context.user_data['current_effect_choice']
    return await _return_to_image_effects_menu(update, context)

async def handle_post_max_image_effects_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if 'Start Processing' in choice:
        selected = context.user_data.get('selected_image_effects', [])
        effects_to_apply_names = [eff[0] if isinstance(eff, tuple) else eff for eff in selected]
        await update.message.reply_text(f"Applying effects: {', '.join(effects_to_apply_names)}. Please wait...", reply_markup=ReplyKeyboardRemove())
        return await process_and_confirm_image_effects(update, context)
    elif 'Reset Selection' in choice:
        context.user_data['selected_image_effects'] = []
        await update.message.reply_text("Your effect selection has been reset.")
        return await _return_to_image_effects_menu(update, context)
    return await cancel(update, context)

# --- LUT Browser Implementation ---

async def _display_image_lut_browser(update: Update, context: ContextTypes.DEFAULT_TYPE, path: str) -> int:
    context.user_data['lut_browser_path'] = path
    items = sorted(os.listdir(path))
    subdirs = [f"📁 {item}" for item in items if os.path.isdir(os.path.join(path, item))]
    cube_files = [f"🧊 {item.replace('.CUBE', '').replace('.cube', '')}" for item in items if item.lower().endswith('.cube')]
    keyboard_items = subdirs + cube_files
    keyboard = [keyboard_items[i:i + 2] for i in range(0, len(keyboard_items), 2)]
    nav_buttons = []
    if path != 'assets/luts':
        nav_buttons.append('⬅️ Back')
    nav_buttons.append('❌ Cancel')
    keyboard.append(nav_buttons)
    await update.message.reply_text(f"Browsing: {path}", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return States.BROWSE_IMAGE_LUTS

async def ask_image_lut_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if 'Built-in' in choice:
        return await _display_image_lut_browser(update, context, 'assets/luts')
    elif 'Upload' in choice:
        await update.message.reply_text("Please upload your .cube file as a document.")
        return States.RECEIVE_IMAGE_LUT_FILE
    return await cancel(update, context)

async def browse_image_luts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    current_path = context.user_data.get('lut_browser_path', 'assets/luts')

    if choice == '⬅️ Back':
        parent_path = str(pathlib.Path(current_path).parent)
        return await _display_image_lut_browser(update, context, parent_path)

    if choice.startswith('📁 '):
        dir_name = choice.replace('📁 ', '')
        new_path = os.path.join(current_path, dir_name)
        return await _display_image_lut_browser(update, context, new_path)

    lut_name = choice.replace('🧊 ', '')
    lut_path = os.path.join(current_path, f"{lut_name}.cube")
    if not os.path.exists(lut_path):
        lut_path = os.path.join(current_path, f"{lut_name}.CUBE")
        if not os.path.exists(lut_path):
            await update.message.reply_text("Error: LUT file not found. Please try again.")
            return await _display_image_lut_browser(update, context, current_path)

    selected = context.user_data.get('selected_image_effects', [])
    selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
    if len(selected) < 3:
        selected.append(('look-up table', lut_path))
        context.user_data['selected_image_effects'] = selected
        await update.message.reply_text(f"Effect '{lut_name}' added.")
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_IMAGE_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You already have 3 effects. Remove one to add another.")
    return await _return_to_image_effects_menu(update, context)

async def receive_image_lut_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document or not update.message.document.file_name.lower().endswith('.cube'):
        await update.message.reply_text("That's not a .cube file. Please upload a valid LUT file.")
        return States.RECEIVE_IMAGE_LUT_FILE
    doc = await update.message.document.get_file()
    downloads_path = context.application.bot_data['downloads_path']
    lut_path = os.path.join(downloads_path, f"custom_img_{doc.file_id}.cube")
    await doc.download_to_drive(lut_path)
    selected = context.user_data.get('selected_image_effects', [])
    selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
    if len(selected) < 3:
        selected.append(('look-up table', lut_path))
        context.user_data['selected_image_effects'] = selected
        await update.message.reply_text(f"Custom LUT '{doc.file_name}' added.")
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_IMAGE_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You already have 3 effects. Remove one to add another.")
    return await _return_to_image_effects_menu(update, context)

# --- Final Confirmation ---

async def process_and_confirm_image_effects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Applies the selected effects to all images and asks for confirmation."""
    engine = ImageEffectsEngine()
    effects_to_apply = context.user_data.get('selected_image_effects', [])
    original_files = context.user_data.get('final_files', [])
    image_files = [f for f in original_files if not is_video_file(f)]
    video_files = [f for f in original_files if is_video_file(f)]
    new_final_files = video_files
    downloads_path = context.application.bot_data['downloads_path']
    for i, file_path in enumerate(image_files):
        output_path = os.path.join(downloads_path, f"effects_{i}_{os.path.basename(file_path)}")
        try:
            path = await asyncio.to_thread(
                engine.apply_effects_in_sequence,
                image_path=file_path,
                effects=effects_to_apply,
                output_path=output_path
            )
            new_final_files.append(path)
        except Exception as e:
            logging.error(f"Error applying image effects to {file_path}: {e}")
            await update.message.reply_text(f"❌ An error occurred while applying effects to {os.path.basename(file_path)}.")
            new_final_files.append(file_path)
    context.user_data['final_files_with_effects'] = new_final_files
    await update.message.reply_text('Preview of images with effects:')
    media_group = [InputMediaPhoto(media=open(f, 'rb')) for f in new_final_files if not is_video_file(f)]
    if media_group:
        await update.message.reply_media_group(media=media_group)
    await update.message.reply_text(
        'Confirm final result with image effects?',
        reply_markup=ReplyKeyboardMarkup([['✅ Yes, continue', '❌ No, restart image effects'], ['❌ Cancel']], one_time_keyboard=True)
    )
    return States.CONFIRM_IMAGE_EFFECTS

async def handle_image_effects_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's confirmation for the applied image effects."""
    if 'Yes' in update.message.text:
        context.user_data['final_files'] = context.user_data['final_files_with_effects']
        await update.message.reply_text('Image effects confirmed. Please enter the final caption.', reply_markup=ReplyKeyboardRemove())
        return States.CAPTION
    else:
        context.user_data['selected_image_effects'] = []
        await update.message.reply_text("Restarting image effect selection...")
        return await ask_image_effects(update, context)
