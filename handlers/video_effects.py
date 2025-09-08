import asyncio
import logging
import os
import pathlib

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaVideo
from telegram.ext import ContextTypes

from add_video_effects import EffectsEngine
from state_machine import States
from handlers.common import is_video_file, cancel

# --- Main Effect Selection Handlers ---

async def ask_video_effects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to select video effects."""
    if 'selected_effects' not in context.user_data:
        context.user_data['selected_effects'] = []
    return await _return_to_effects_menu(update, context)


async def _return_to_effects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main effects menu and current selections without clearing them."""
    engine = EffectsEngine()
    effects_list = list(engine.effects_map.keys())
    
    keyboard = [effects_list[i:i + 3] for i in range(0, len(effects_list), 3)]
    keyboard.append(['✅ Done Selecting', '🔄 Reset', '❌ Cancel'])
    
    selected = context.user_data.get('selected_effects', [])
    
    if not selected:
        effect_text = "Current effects: None."
    else:
        effect_lines = []
        for i, eff in enumerate(selected):
            if isinstance(eff, tuple):
                name = f"{eff[0]} ({eff[1]})"
                if eff[0] == 'look-up table':
                    name = f"{eff[0]} ({os.path.basename(eff[1])})"
                effect_lines.append(f"{i+1}. {name}")
            else:
                effect_lines.append(f"{i+1}. {eff}")
        effect_text = "Current effects:\n" + "\n".join(effect_lines)

    await update.message.reply_text(
        f"{effect_text}\n\n"
        "Select another effect, click an existing one to remove it, or press 'Done Selecting'.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return States.CHOOSE_EFFECTS

async def choose_effects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user's selection of video effects, branching to sub-conversations for parameterized effects."""
    choice = update.message.text
    if choice == '❌ Cancel':
        return await cancel(update, context)

    if choice == '🔄 Reset':
        context.user_data['selected_effects'] = []
        return await _return_to_effects_menu(update, context)
        
    selected = context.user_data.get('selected_effects', [])

    if 'Done' in choice:
        if not selected:
            await update.message.reply_text("No effects selected. Please enter the final caption.", reply_markup=ReplyKeyboardRemove())
            return States.CAPTION
        else:
            return await _ask_render_quality(update, context)

    # --- Parameterized Effect Routing ---
    if choice == 'look-up table' and any(isinstance(eff, tuple) and eff[0] == 'look-up table' for eff in selected):
        # The user wants to change/remove the existing LUT.
        # The simplest way is to remove the old one and start the selection process over.
        context.user_data['selected_effects'] = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
        await update.message.reply_text("Previous LUT removed. Please select a new one.")
        # Fall through to start the LUT selection process

    parameterized_effects = {
        'look-up table': (States.ASK_LUT_TYPE, [['📁 Built-in', '📤 Upload Custom']]),
        'Ken Burns': (States.ASK_KENBURNS_LEVEL, [['Low', 'Medium', 'High']]),
        'Contrast / Brightness': (States.ASK_CONTRAST_LEVEL, [['Low', 'Medium', 'High']]),
        'Color Saturation': (States.ASK_SATURATION_LEVEL, [['Low', 'Medium', 'High']]),
        'Chromatic Aberration': (States.ASK_ABERRATION_LEVEL, [['Low', 'Medium', 'High']]),
        'Pixelated Effect': (States.ASK_PIXELATE_LEVEL, [['Low', 'Medium', 'High']]),
        'Speed Control': (States.ASK_SPEED_LEVEL, [['1.25x', '1.5x', '2.0x']]),
        'Rotate': (States.ASK_ROTATE_OPTION, [['15°', '45°', '90°']]),
        'Film Grain': (States.ASK_GRAIN_LEVEL, [['Low', 'Medium', 'High']]),
        'Glitch': (States.ASK_GLITCH_LEVEL, [['Low', 'Medium', 'High']]),
        'Rolling Shutter': (States.ASK_SHUTTER_LEVEL, [['Low', 'Medium', 'High']]),
        'Neon Glow': (States.ASK_NEON_LEVEL, [['Low', 'Medium', 'High']]),
        'Cartoon / Painterly': (States.ASK_CARTOON_LEVEL, [['Subtle', 'Normal', 'Strong']]),
        'Vignette': (States.ASK_VIGNETTE_LEVEL, [['Low', 'Medium', 'High']]),
        'Fade In/Out': (States.ASK_FADE_DURATION, [['1.0s', '1.5s', '2.0s']]),
    }

    if choice in parameterized_effects:
        state, options = parameterized_effects[choice]
        keyboard = options + [['❌ Cancel']]
        await update.message.reply_text(
            f"Please choose an option for {choice}:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return state

    # --- Standard (non-parameterized) effect selection ---
    if any(eff == choice or (isinstance(eff, tuple) and eff[0] == choice) for eff in selected):
        selected = [eff for eff in selected if not (eff == choice or (isinstance(eff, tuple) and eff[0] == choice))]
        context.user_data['selected_effects'] = selected
    elif len(selected) < 3:
        selected.append(choice)
        context.user_data['selected_effects'] = selected
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text(
                "You have selected the maximum of 3 effects.",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.POST_MAX_VIDEO_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You can only select up to 3 effects.")

    return await _return_to_effects_menu(update, context)


def create_level_setter(effect_name: str, option_map: dict, default_value: str):
    """A factory to create a handler for setting an effect's level."""
    async def level_setter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        choice = update.message.text
        level = option_map.get(choice.lower(), default_value)
        selected = context.user_data.get('selected_effects', [])
        selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == effect_name)]
        
        if len(selected) < 3:
            selected.append((effect_name, level))
            context.user_data['selected_effects'] = selected
            if len(selected) == 3:
                keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
                await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
                return States.POST_MAX_VIDEO_EFFECTS_CHOICE
        else:
            await update.message.reply_text("You already have 3 effects. Remove one to add another.")

        return await _return_to_effects_menu(update, context)
    return level_setter

async def handle_post_max_effects_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice after selecting 3 effects."""
    choice = update.message.text
    if 'Start Processing' in choice:
        return await _ask_render_quality(update, context)
    elif 'Reset Selection' in choice:
        context.user_data['selected_effects'] = []
        await update.message.reply_text("Your effect selection has been reset.")
        return await _return_to_effects_menu(update, context)
    else: # Cancel
        return await cancel(update, context)

async def _ask_render_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the message to ask for render quality."""
    keyboard = [['🚀 High Quality', '⚡️ Draft Preview'], ['❌ Cancel']]
    await update.message.reply_text(
        "How would you like to render the preview?\n\n"
        "🚀 **High Quality:** Slower, but shows the final result.\n"
        "⚡️ **Draft Preview:** Much faster, but lower quality.",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True),
        parse_mode='Markdown'
    )
    return States.ASK_RENDER_QUALITY

# --- LUT Browser Implementation ---

async def _display_lut_browser(update: Update, context: ContextTypes.DEFAULT_TYPE, path: str) -> int:
    """Displays a file browser for the LUTs directory."""
    context.user_data['lut_browser_path'] = path
    
    items = sorted(os.listdir(path))
    subdirs = [f"📁 {item}" for item in items if os.path.isdir(os.path.join(path, item))]
    cube_files = [f"🧊 {item.replace('.CUBE', '').replace('.cube', '')}" for item in items if item.lower().endswith('.cube')]
    
    keyboard_items = subdirs + cube_files
    keyboard = [keyboard_items[i:i + 3] for i in range(0, len(keyboard_items), 3)]
    
    # Add navigation buttons
    nav_buttons = []
    if path != 'assets/luts':
        nav_buttons.append('⬅️ Back')
    nav_buttons.append('❌ Cancel')
    keyboard.append(nav_buttons)
    
    await update.message.reply_text(f"Browsing: {path}", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return States.BROWSE_VIDEO_LUTS

async def ask_lut_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the initial choice for LUT type (Built-in or Upload)."""
    choice = update.message.text
    if 'Built-in' in choice:
        return await _display_lut_browser(update, context, 'assets/luts')
    elif 'Upload' in choice:
        await update.message.reply_text("Please upload your .cube file as a document.")
        return States.RECEIVE_LUT_FILE
    return await cancel(update, context)

async def browse_video_luts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles navigation and selection within the LUT browser."""
    choice = update.message.text
    current_path = context.user_data.get('lut_browser_path', 'assets/luts')

    if choice == '⬅️ Back':
        parent_path = str(pathlib.Path(current_path).parent)
        return await _display_lut_browser(update, context, parent_path)

    # Check if the choice is a directory
    if choice.startswith('📁 '):
        dir_name = choice.replace('📁 ', '')
        new_path = os.path.join(current_path, dir_name)
        return await _display_lut_browser(update, context, new_path)

    # Otherwise, it's a file selection
    lut_name = choice.replace('🧊 ', '')
    lut_path = os.path.join(current_path, f"{lut_name}.cube")
    if not os.path.exists(lut_path):
         lut_path = os.path.join(current_path, f"{lut_name}.CUBE") # Check uppercase
         if not os.path.exists(lut_path):
            await update.message.reply_text("Error: LUT file not found. Please try again.")
            return await _display_lut_browser(update, context, current_path)

    # Add the effect
    selected = context.user_data.get('selected_effects', [])
    selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
    if len(selected) < 3:
        selected.append(('look-up table', lut_path))
        context.user_data['selected_effects'] = selected
        await update.message.reply_text(f"Effect '{lut_name}' added.")
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_VIDEO_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You already have 3 effects. Remove one to add another.")

    return await _return_to_effects_menu(update, context)

async def receive_lut_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles receiving a custom uploaded .cube file."""
    if not update.message.document or not update.message.document.file_name.lower().endswith('.cube'):
        await update.message.reply_text("That's not a .cube file. Please upload a valid LUT file.")
        return States.RECEIVE_LUT_FILE
        
    doc = await update.message.document.get_file()
    downloads_path = context.application.bot_data['downloads_path']
    lut_path = os.path.join(downloads_path, f"custom_{doc.file_id}.cube")
    await doc.download_to_drive(lut_path)

    selected = context.user_data.get('selected_effects', [])
    selected = [eff for eff in selected if not (isinstance(eff, tuple) and eff[0] == 'look-up table')]
    if len(selected) < 3:
        selected.append(('look-up table', lut_path))
        context.user_data['selected_effects'] = selected
        await update.message.reply_text(f"Custom LUT '{doc.file_name}' added.")
        if len(selected) == 3:
            keyboard = [['🚀 Start Processing', '🔄 Reset Selection'], ['❌ Cancel']]
            await update.message.reply_text("You have selected the maximum of 3 effects.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return States.POST_MAX_VIDEO_EFFECTS_CHOICE
    else:
        await update.message.reply_text("You already have 3 effects. Remove one to add another.")
    
    return await _return_to_effects_menu(update, context)

# --- Final Processing and Confirmation ---

async def handle_render_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    quality = 'draft' if 'Draft' in choice else 'final'
    effect_names = [eff[0] if isinstance(eff, tuple) else eff for eff in context.user_data.get('selected_effects', [])]
    await update.message.reply_text(f"Applying effects: {', '.join(effect_names)}. Please wait, this may take a moment...", reply_markup=ReplyKeyboardRemove())
    return await process_and_confirm_effects(update, context, quality=quality)

async def process_and_confirm_effects(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str = 'final') -> int:
    engine = EffectsEngine()
    effects_applied_files = []
    for i, file_path in enumerate(context.user_data['final_files']):
        if is_video_file(file_path):
            output_path = os.path.join(context.application.bot_data['downloads_path'], f"effects_{i}_{os.path.basename(file_path)}")
            try:
                path = await asyncio.to_thread(
                    engine.apply_effects_in_sequence,
                    video_path=file_path,
                    effects=context.user_data['selected_effects'],
                    output_path=output_path,
                    quality=quality
                )
                effects_applied_files.append(path)
            except Exception as e:
                logging.error(f"Error applying effects to {file_path}: {e}")
                await update.message.reply_text(f"❌ An error occurred while applying effects to {os.path.basename(file_path)}.")
                effects_applied_files.append(file_path)
        else:
            effects_applied_files.append(file_path)
    context.user_data['final_files_with_effects'] = effects_applied_files
    await update.message.reply_text('Preview of video(s) with effects:')
    media_group = [InputMediaVideo(media=open(f, 'rb')) for f in effects_applied_files if is_video_file(f)]
    if media_group:
        await update.message.reply_media_group(media=media_group)
    await update.message.reply_text(
        'Confirm final result with effects?',
        reply_markup=ReplyKeyboardMarkup([['✅ Yes, upload', '❌ No, restart effects'], ['❌ Cancel']], one_time_keyboard=True)
    )
    return States.CONFIRM_EFFECTS

async def handle_effects_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'Yes' in update.message.text:
        context.user_data['final_files'] = context.user_data['final_files_with_effects']
        await update.message.reply_text('Effects confirmed. Please enter the final caption.', reply_markup=ReplyKeyboardRemove())
        return States.CAPTION
    else:
        # Reset selections and go back to the start of the effects menu
        context.user_data['selected_effects'] = []
        await update.message.reply_text("Restarting effect selection...")
        return await _return_to_effects_menu(update, context)

# Create handlers for each parameterized effect
set_contrast_level = create_level_setter('Contrast / Brightness', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_saturation_level = create_level_setter('Color Saturation', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_aberration_level = create_level_setter('Chromatic Aberration', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_pixelate_level = create_level_setter('Pixelated Effect', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_speed_level = create_level_setter('Speed Control', {'1.25x': 'low', '1.5x': 'medium', '2.0x': 'high'}, '1.5x')
set_rotate_option = create_level_setter('Rotate', {'15°': 'low', '45°': 'medium', '90°': 'high'}, '90°')
set_grain_level = create_level_setter('Film Grain', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_glitch_level = create_level_setter('Glitch', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_shutter_level = create_level_setter('Rolling Shutter', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_neon_level = create_level_setter('Neon Glow', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_cartoon_level = create_level_setter('Cartoon / Painterly', {'Subtle': 'low', 'Normal': 'medium', 'Strong': 'high'}, 'medium')
set_vignette_level = create_level_setter('Vignette', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
set_fade_duration = create_level_setter('Fade In/Out', {'1.0s': 'low', '1.5s': 'medium', '2.0s': 'high'}, '1.5s')
set_kenburns_level = create_level_setter('Ken Burns', {'Low': 'low', 'Medium': 'medium', 'High': 'high'}, 'medium')
