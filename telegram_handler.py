from telegram.ext import MessageHandler, CommandHandler, filters, ConversationHandler

from state_machine import States
from handlers import auth, common, media, watermark, music, video_effects, upload, image_effects

def get_conversation_handler() -> ConversationHandler:
    """
    Builds the main conversation handler by assembling handlers from sub-modules.
    """
    return ConversationHandler(
        entry_points=[CommandHandler('start', auth.start)],
        states={
            # A state to handle restarting the conversation
            States.START: [MessageHandler(filters.ALL, auth.start)],

            # Authentication
            States.AUTH_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.handle_2fa)],
            States.AUTH_SMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.handle_sms)],

            # Media Handling
            States.MEDIA_TYPE: [MessageHandler(filters.Regex('^📤 Album$|^📎 Single$'), media.handle_media_type)],
            States.RECEIVE_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION, media.handle_media),
                MessageHandler(filters.TEXT & filters.Regex(r'^🏁 Done$'), media.process_media)
            ],
            States.CONFIRM: [MessageHandler(filters.Regex('^✅ Yes, continue$|^❌ No, Upload As Is$'), media.handle_confirmation)],
            
            # Image Watermark
            States.ASK_IMAGE_WATERMARK: [MessageHandler(filters.Regex('^Yes$|^No$'), watermark.ask_image_watermark)],
            States.RECEIVE_IMAGE_WATERMARK: [MessageHandler(filters.PHOTO, watermark.receive_image_watermark)],
            States.CHOOSE_IMG_WATERMARK_POSITION: [MessageHandler(filters.Regex('^(top|middle|bottom)-(left|center|right)$'), watermark.handle_img_position)],
            States.CHOOSE_IMG_WATERMARK_SCALE: [MessageHandler(filters.Regex(r'^\d+$'), watermark.handle_img_scale)],
            States.CHOOSE_IMG_WATERMARK_OPACITY: [MessageHandler(filters.Regex(r'^\d+$'), watermark.generate_and_preview_image_watermark)],
            States.CONFIRM_IMG_WATERMARK: [MessageHandler(filters.Regex('^✅ Yes, Confirm$|^❌ No, Retry$'), watermark.handle_img_watermark_confirmation)],
            
            # Text Watermark
            States.ASK_TEXT_WATERMARK: [MessageHandler(filters.Regex('^Yes$|^No$'), watermark.handle_ask_text_watermark)],
            States.RECEIVE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, watermark.receive_text)],
            States.CHOOSE_FONT: [MessageHandler(filters.TEXT & ~filters.COMMAND, watermark.handle_font)],
            States.CHOOSE_FONT_SIZE: [MessageHandler(filters.Regex(r'^\d+$'), watermark.handle_font_size)],
            States.CHOOSE_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, watermark.handle_color)],
            States.CHOOSE_TEXT_POSITION: [MessageHandler(filters.Regex('^top–center$|^middle–center$|^bottom–center$'), watermark.generate_and_preview_text_watermark)],
            States.CONFIRM_TEXT_WATERMARK: [MessageHandler(filters.Regex('^✅ Yes, Confirm$|^❌ No, Retry$'), watermark.handle_text_watermark_confirmation)],
            
            # Music
            States.ASK_ADD_MUSIC: [MessageHandler(filters.Regex('^Yes$|^No$'), music.ask_add_music)],
            States.RECEIVE_MUSIC: [MessageHandler(filters.AUDIO, music.receive_music)],
            States.RECEIVE_MUSIC_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, music.receive_music_start_time)],
            States.CONFIRM_MUSIC: [MessageHandler(filters.Regex('^✅ Yes, Confirm$|^❌ No, Retry$'), music.handle_music_confirmation)],
            
            # Combination & Final Processing
            States.CONFIRM_COMBINED_MEDIA: [MessageHandler(filters.Regex('^✅ Yes, continue$|^❌ No, restart edits$'), upload.handle_combined_media_confirmation)],
            States.CONFIRM_FINAL_MEDIA: [MessageHandler(filters.Regex('^✅ Yes, looks good$|^❌ No, restart edits$|^Add Video Effects$|^Add Image Effects$'), upload.handle_final_confirmation)],
            
            # Video Effects
            States.ASK_VIDEO_EFFECTS: [MessageHandler(filters.Regex('Add Video Effects'), video_effects.ask_video_effects)],
            States.CHOOSE_EFFECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, video_effects.choose_effects)],
            States.CONFIRM_EFFECTS: [MessageHandler(filters.Regex('^✅ Yes, upload$|^❌ No, restart effects$'), video_effects.handle_effects_confirmation)],

            # Image Effects
            States.ASK_IMAGE_EFFECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, image_effects.ask_image_effects)],
            States.CHOOSE_IMAGE_EFFECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, image_effects.choose_image_effects)],
            States.CONFIRM_IMAGE_EFFECTS: [MessageHandler(filters.Regex('^✅ Yes, continue$|^❌ No, restart image effects$'), image_effects.handle_image_effects_confirmation)],
            States.ASK_IMAGE_EFFECT_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$|^15°$|^45°$|^90°$'), image_effects.set_image_effect_level)],
            States.POST_MAX_IMAGE_EFFECTS_CHOICE: [MessageHandler(filters.Regex('^🚀 Start Processing$|^🔄 Reset Selection$'), image_effects.handle_post_max_image_effects_choice)],

            # Video Effects
            States.POST_MAX_VIDEO_EFFECTS_CHOICE: [MessageHandler(filters.Regex('^🚀 Start Processing$|^🔄 Reset Selection$'), video_effects.handle_post_max_effects_choice)],
            
            # LUT Sub-conversation
            States.ASK_LUT_TYPE: [MessageHandler(filters.Regex('^📁 Built-in$|^📤 Upload Custom$'), video_effects.ask_lut_type)],
            States.BROWSE_VIDEO_LUTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, video_effects.browse_video_luts)],
            States.RECEIVE_LUT_FILE: [MessageHandler(filters.Document.ALL, video_effects.receive_lut_file)],
            
            States.ASK_IMAGE_LUT_TYPE: [MessageHandler(filters.Regex('^📁 Built-in$|^📤 Upload Custom$'), image_effects.ask_image_lut_type)],
            States.BROWSE_IMAGE_LUTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, image_effects.browse_image_luts)],
            States.RECEIVE_IMAGE_LUT_FILE: [MessageHandler(filters.Document.ALL, image_effects.receive_image_lut_file)],

            # Parameterization Sub-conversations
            States.ASK_CONTRAST_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_contrast_level)],
            States.ASK_SATURATION_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_saturation_level)],
            States.ASK_ABERRATION_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_aberration_level)],
            States.ASK_PIXELATE_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_pixelate_level)],
            States.ASK_SPEED_LEVEL: [MessageHandler(filters.Regex(r'^1\.25x$|^1\.5x$|^2\.0x$'), video_effects.set_speed_level)],
            States.ASK_ROTATE_OPTION: [MessageHandler(filters.Regex('^15°$|^45°$|^90°$'), video_effects.set_rotate_option)],
            States.ASK_GRAIN_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_grain_level)],
            States.ASK_KENBURNS_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_kenburns_level)],
            States.ASK_GLITCH_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_glitch_level)],
            States.ASK_SHUTTER_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_shutter_level)],
            States.ASK_NEON_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_neon_level)],
            States.ASK_CARTOON_LEVEL: [MessageHandler(filters.Regex('^Subtle$|^Normal$|^Strong$'), video_effects.set_cartoon_level)],
            States.ASK_VIGNETTE_LEVEL: [MessageHandler(filters.Regex('^Low$|^Medium$|^High$'), video_effects.set_vignette_level)],
            States.ASK_FADE_DURATION: [MessageHandler(filters.Regex(r'^1\.0s$|^1\.5s$|^2\.0s$'), video_effects.set_fade_duration)],

            # Render Quality
            States.ASK_RENDER_QUALITY: [MessageHandler(filters.Regex('^🚀 High Quality$|^⚡️ Draft Preview$'), video_effects.handle_render_quality)],
            
            # Finalize
            States.CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload.handle_caption_and_upload)],
        },
        fallbacks=[
            CommandHandler('cancel', common.cancel),
            MessageHandler(filters.Regex('^❌ Cancel$'), common.cancel)
        ],
        conversation_timeout=1440,  # 24 minutes
        allow_reentry=True
    )
