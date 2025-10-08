# services/photo_handler.py - Handler untuk foto eviden
import os
import logging
import tempfile
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

FORM_SECTION, UPLOAD_PHOTO = 1, 4

logger = logging.getLogger(__name__)

class PhotoHandler:
    def __init__(self, google_services, session_service):
        self.google_services = google_services
        self.session_service = session_service

    def get_current_google_service(self, user_id):
        """Get Google service based on current form type"""
        session = self.session_service.get_session(user_id)
        form_type = session.get('form_type', 'wifi') if session else 'wifi'
        return self.google_services.get(form_type)


    async def show_photo_menu(self, update, context, user_id):
        """Show photo upload menu dengan opsi hapus semua - FIXED"""
        try:
            session = self.session_service.get_session(user_id)
            if not session:
                return None, "Session tidak ditemukan"
            excel_generated = session.get('excel_generated', False)
            if not excel_generated:
                # Buat keyboard untuk kembali
                keyboard = [[InlineKeyboardButton("🔙 Kembali ke Form", callback_data="back_form")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                error_message = (
                    "⚠️ **Excel Belum Digenerate**\n\n"
                    "Upload foto evidence hanya bisa dilakukan setelah Excel berhasil digenerate.\n"
                    "Silakan generate Excel terlebih dahulu."
                )
                return reply_markup, error_message

            photos = session.get('photos', [])
            photo_count = len(photos)
            
            menu_text = "📷 **Upload Foto Eviden**\n\n"
            
            if photo_count > 0:
                menu_text += f"📊 **Status:** {photo_count} foto terupload\n\n"
                menu_text += "📋 **Fitur:**\n"
                menu_text += "• Kirim foto untuk upload tambahan\n"
                menu_text += "• Foto akan terus ditambahkan sampai pilih 'Selesai'\n"
                menu_text += "• Pilih 'Hapus Semua' untuk mulai dari awal\n\n"
            else:
                menu_text += "📊 **Status:** Belum ada foto terupload\n\n"
                menu_text += "📋 **Fitur:**\n"
                menu_text += "• Kirim foto untuk upload (bisa banyak sekaligus)\n"
                menu_text += "• Foto akan terus ditambahkan sampai pilih 'Selesai'\n\n"
            
            menu_text += "Pilih opsi:"
            
            keyboard = [
                [InlineKeyboardButton("📷 Upload Foto Baru", callback_data="upload_new_photo")],
            ]
            
            # PERBAIKAN: Selalu tampilkan opsi untuk melihat dan menghapus foto jika ada
            if photo_count > 0:
                keyboard.extend([
                    [InlineKeyboardButton("👁️ Lihat Daftar Foto", callback_data="view_photos")],
                    [InlineKeyboardButton("🗑️ Hapus Semua Foto", callback_data="delete_all_photos")],
                    [InlineKeyboardButton("✅ Selesai Upload", callback_data="finish_upload")]
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Kembali ke Form", callback_data="back_form")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            return reply_markup, menu_text
            
        except Exception as e:
            logger.error(f"❌ Error showing photo menu: {e}")
            return None, "Terjadi kesalahan"

        
    async def handle_photo_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo-related callback queries"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            data = query.data
            
            if data == "upload_new_photo":
                await self.start_photo_upload_mode(update, context, user_id)
                return "photo_upload"
                
            elif data == "view_photos":
                photo_list = await self.view_uploaded_photos(update, context, user_id)
                await query.edit_message_text(photo_list)
                return "photo_menu"
                
            elif data == "delete_all_photos":
                success, message = await self.delete_all_photos(update, context, user_id)
                if success and message == "confirm_pending":
                    return "photo_confirm_delete"
                await query.edit_message_text(message)
                return "photo_menu"
                
            elif data == "confirm_delete_photos":
                success, message = await self.confirm_delete_photos(update, context, user_id)
                await query.edit_message_text(message)
                return "photo_menu"
                
            elif data == "cancel_delete_photos":
                return await self.show_photo_menu(update, context, user_id)
                
            elif data == "finish_upload":
                # Clear photo upload mode and return to form
                context.user_data.pop('photo_upload_mode', None)
                await query.edit_message_text("✅ Upload foto selesai")
                return "form_menu"
                
            elif data == "back_form":
                context.user_data.pop('photo_upload_mode', None)
                await query.edit_message_text("Kembali ke formulir")
                return "form_menu"
                
        except Exception as e:
            logger.error(f"Error in handle_photo_callback: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan")
            return "photo_menu"

    async def handle_photo_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo upload from user to the evidence folder"""
        temp_file = None
        try:
            user_id = update.effective_user.id
            
            # Check if user is in photo upload mode
            upload_mode = context.user_data.get('photo_upload_mode')
            if not upload_mode:
                await update.message.reply_text(
                    "📷 Untuk upload foto, silakan pilih menu 'Upload Foto Eviden' dari formulir."
                )
                return False
            
            session = self.session_service.get_session(user_id)
            if not session:
                await update.message.reply_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                return False
            
            # Check if we have an evidence folder from Excel generation
            evidence_folder_id = session.get('evidence_folder_id')
            if not evidence_folder_id:
                await update.message.reply_text(
                    "❌ Folder evidence belum dibuat. Silakan generate Excel terlebih dahulu."
                )
                return False
            
            # Get photo with highest resolution
            photo = update.message.photo[-1]
            
            # Send processing message
            processing_msg = await update.message.reply_text("⏳ Sedang mengupload foto ke folder evidence...")
            
            try:
                # Get file from Telegram
                file = await context.bot.get_file(photo.file_id)
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                await file.download_to_drive(temp_file.name)
                temp_file.close()
                
                # Generate filename
                photo_count = len(session.get('photos', [])) + 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"evidence_{photo_count}_{timestamp}.jpg"
                
                # Upload to Google Drive evidence folder
                google_service = self.get_current_google_service(user_id)
                file_id = google_service.upload_photo_evidence(
                    temp_file.name, filename, evidence_folder_id,
                )
                
                # Clean up temp file
                if temp_file and os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
                
                if file_id:
                    # Save photo info to session
                    photo_info = {
                        'filename': filename,
                        'file_id': file_id,
                        'description': f"Evidence photo {photo_count}",
                        'uploaded_at': datetime.now().isoformat()
                    }
                    
                    self.session_service.add_photo(user_id, photo_info)
                    
                    # Get evidence folder link
                    google_service = self.get_current_google_service(user_id)
                    evidence_link = google_service.get_folder_link(evidence_folder_id)
                    
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=processing_msg.message_id,
                        text=f"✅ Foto berhasil diupload ke folder evidence!\n\n"
                            f"📷 **File:** {filename}\n"
                            f"📁 **Folder:** {evidence_link}\n\n"
                            f"💡 Kirim foto lain langsung atau gunakan tombol selesai."
                    )
                    context.user_data['photo_upload_mode'] = True
                    return UPLOAD_PHOTO
                    
                else:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=processing_msg.message_id,
                        text="❌ Gagal mengupload foto ke Google Drive. Silakan coba lagi."
                    )
                    return False
                    
            except Exception as upload_error:
                logger.error(f"❌ Error during photo upload: {upload_error}")
                
                # Clean up temp file if exists
                try:
                    if temp_file and os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not clean up temp file: {cleanup_error}")
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=processing_msg.message_id,
                    text=f"❌ Terjadi kesalahan saat upload: {str(upload_error)[:100]}..."
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in handle_photo_upload: {e}")
            # Clean up jika ada file temporary yang tertinggal
            try:
                if temp_file and os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            except:
                pass
            await update.message.reply_text("❌ Terjadi kesalahan saat upload foto.")
            return False

    async def handle_photo_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input during photo upload state"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            if not message_text or message_text.strip() == "":
                message_text = "default"
            
            # PERBAIKAN: Handle /selesai command dengan cleanup yang benar
            if message_text in ["/selesai", "✅ Selesai Upload Foto", "selesai", "Selesai"]:
                # Clear photo upload mode
                context.user_data.pop('photo_upload_mode', None)
                
                # Remove keyboard dengan ReplyKeyboardRemove
                from telegram import ReplyKeyboardRemove
                await update.message.reply_text("✅ Upload foto selesai!", reply_markup=ReplyKeyboardRemove())
                
                # Get current photos count
                photos = self.session_service.get_photos(user_id)
                
                success_text = f"✅ **Upload Foto Selesai**\n\n"
                success_text += f"📊 Total foto terupload: {len(photos)} foto\n\n"
                google_service = self.get_current_google_service(user_id)
                
                if photos:
                    evidence_folder_id = self.session_service.get_session(user_id).get('evidence_folder_id')
                    if evidence_folder_id:
                        folder_link = google_service.get_folder_link(evidence_folder_id)

                        success_text += f"📁 **Link folder:** {folder_link}\n\n"
                
                success_text += "Foto eviden berhasil disimpan ke Google Drive."
                
                await self.safe_send_message(context, update.effective_chat.id, success_text, parse_mode='Markdown')
                
                # Kembali ke form menu
                return "form_menu"
                
            elif message_text in ["🔙 Kembali ke Form", "kembali", "Kembali", "batal", "Batal"]:
                # Clear photo upload mode
                context.user_data.pop('photo_upload_mode', None)
                
                # Remove keyboard
                remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
                await update.message.reply_text("Kembali ke form", reply_markup=remove_keyboard)
                
                # Kembali ke form menu
                return "form_menu"
            
            else:
                # PERBAIKAN: Tampilkan keyboard untuk selesai upload
                keyboard = [
                    [KeyboardButton("✅ Selesai Upload Foto")],
                    [KeyboardButton("🔙 Kembali ke Form")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    "📷 Silakan kirim foto lagi atau pilih 'Selesai Upload Foto' untuk berhenti.",
                    reply_markup=reply_markup
                )
                return UPLOAD_PHOTO
                
        except Exception as e:
            logger.error(f"❌ Error in handle_photo_text_input: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
            return UPLOAD_PHOTO

    # PERBAIKAN: Tambahkan method safe_send_message untuk menghindari error teks kosong
    async def safe_send_message(self, context, chat_id, text, **kwargs):
        """Safe method to send messages with empty text validation"""
        if not text or text.strip() == "":
            text = "📋 Data tidak tersedia"
        
        try:
            return await context.bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None

    async def start_photo_upload_mode(self, update, context, user_id):
        """Start photo upload mode - FIXED"""
        try:
            # PERBAIKAN 4: Validasi Excel dulu sebelum mulai upload
            session = self.session_service.get_session(user_id)
            excel_generated = session.get('excel_generated', False) if session else False
            
            if not excel_generated:
                error_msg = (
                    "⚠️ **Tidak Dapat Upload Foto**\n\n"
                    "Excel belum digenerate. Silakan generate Excel terlebih dahulu "
                    "untuk membuat folder evidence."
                )
                
                # Buat keyboard kembali
                keyboard = [[InlineKeyboardButton("🔙 Kembali ke Form", callback_data="back_form")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(
                        error_msg, 
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        error_msg,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                
                return False
            
            # Set photo upload mode
            context.user_data['photo_upload_mode'] = True
            
            upload_text = (
                "📷 **Mode Upload Foto Aktif**\n\n"
                "Silakan kirim foto-foto eviden.\n"
                "Setiap foto akan otomatis disimpan ke folder Google Drive.\n\n"
                "📋 **Cara penggunaan:**\n"
                "• Kirim foto langsung (bisa berurutan)\n"
                "• Ketik /selesai untuk mengakhiri upload\n"
                "• Gunakan tombol di bawah untuk navigasi\n\n"
                "📤 Kirim foto pertama atau berikutnya:"
            )

            keyboard = [
                [KeyboardButton("✅ /selesai - Selesai Upload")],
                [KeyboardButton("🔙 Kembali ke Form")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(upload_text, parse_mode='Markdown')
                # Kirim pesan terpisah dengan keyboard yang persistent
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="📤 Mode Upload Aktif - Kirim foto langsung atau gunakan tombol:",
                    reply_markup=reply_markup
                )

            else:
                await update.message.reply_text(
                    upload_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting photo upload mode: {e}")
            return False


    async def view_uploaded_photos(self, update, context, user_id):
        """Show list of uploaded photos"""
        try:
            photos = self.session_service.get_photos(user_id)
            
            if not photos:
                return "Belum ada foto yang diupload."
            
            photo_list = "📷 **Daftar Foto Eviden**\n\n"
            
            for i, photo in enumerate(photos, 1):
                filename = photo.get('filename', 'Unknown')
                uploaded_at = photo.get('uploaded_at', '')
                
                try:
                    if uploaded_at:
                        upload_time = datetime.fromisoformat(uploaded_at)
                        time_str = upload_time.strftime("%d/%m/%Y %H:%M")
                    else:
                        time_str = "Unknown time"
                except:
                    time_str = "Unknown time"
                
                photo_list += f"{i}. **{filename}**\n"
                photo_list += f"   📅 {time_str}\n\n"
            
            # Add folder link if available
            session = self.session_service.get_session(user_id)
            evidence_folder_id = session.get('evidence_folder_id')
            google_service = self.get_current_google_service(user_id)
            
            if evidence_folder_id:
                folder_link = google_service.get_folder_link(evidence_folder_id)
                photo_list += f"📁 **Link Folder:** {folder_link}"
            
            return photo_list
            
        except Exception as e:
            logger.error(f"❌ Error viewing photos: {e}")
            return "Terjadi kesalahan saat menampilkan foto."

    async def delete_all_photos(self, update, context, user_id):
        """Delete all uploaded photos with confirmation - FIXED"""
        try:
            session = self.session_service.get_session(user_id)
            if not session:
                return False, "Session tidak ditemukan"
            
            photos = session.get('photos', [])
            
            if not photos:
                # Langsung kembali ke menu foto jika tidak ada foto
                reply_markup, menu_text = await self.show_photo_menu(update, context, user_id)
                await update.callback_query.edit_message_text(
                    f"ℹ️ Tidak ada foto untuk dihapus.\n\n{menu_text}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return True, "no_photos_to_delete"
            
            # Konfirmasi penghapusan
            keyboard = [
                [InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data="confirm_delete_photos")],
                [InlineKeyboardButton("❌ Tidak, Kembali", callback_data="section_photo_evidence")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "⚠️ **Konfirmasi Penghapusan**\n\n"
                f"Anda yakin ingin menghapus semua {len(photos)} foto?\n"
                "Tindakan ini tidak dapat dibatalkan.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return True, "confirm_pending"
            
        except Exception as e:
            logger.error(f"❌ Error in delete_all_photos: {e}")
            return False, "Terjadi kesalahan saat menghapus foto."

    async def confirm_delete_photos(self, update, context, user_id):
        """Confirm and execute photo deletion - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Show processing message first
            await query.edit_message_text("⏳ Menghapus semua foto...")
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan")
                return False, "Session tidak ditemukan"
            
            photos = session.get('photos', [])
            google_service = self.get_current_google_service(user_id)
            deleted_count = 0
            
            # Delete individual photos from Drive
            for photo in photos:
                try:
                    file_id = photo.get('file_id')
                    if file_id:
                        google_service.service_drive.files().delete(fileId=file_id).execute()

                        deleted_count += 1
                        logger.info(f"🗑️ Deleted photo: {photo.get('filename')}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete photo {photo.get('filename')}: {e}")
            
            # Clear photos from session
            self.session_service.clear_photos(user_id)
            
            # Show success message and return to photo menu
            success_text = f"✅ {deleted_count} foto berhasil dihapus!"
            
            # Get updated photo menu (should show no photos now)
            reply_markup, menu_text = await self.show_photo_menu(update, context, user_id)
            
            await query.edit_message_text(
                f"{success_text}\n\n{menu_text}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return True, success_text
            
        except Exception as e:
            logger.error(f"❌ Error confirming photo deletion: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan saat menghapus foto.")
            return False, "Terjadi kesalahan saat menghapus foto."

    def get_photo_section_data(self, user_id):
        """Get photo section status for form display"""
        try:
            photos = self.session_service.get_photos(user_id)
            
            if photos:
                return {
                    'has_photos': True,
                    'photo_count': len(photos),
                    'status': 'completed'
                }
            else:
                return {
                    'has_photos': False,
                    'photo_count': 0,
                    'status': 'empty'
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting photo section data: {e}")
            return {
                'has_photos': False,
                'photo_count': 0,
                'status': 'error'
            }