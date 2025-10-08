# services/session_ba_service.py - Session Management untuk Berita Acara (FIXED)
import json
import os
import logging
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

class SessionBAService:
    def __init__(self):
        # Use temp directory for session file to avoid permission issues
        temp_dir = tempfile.gettempdir()
        self.session_file = os.path.join(temp_dir, 'ba_user_sessions.json')
        logger.info(f"Session file location: {self.session_file}")
    
    def _load_sessions(self):
        """Load sessions from file"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading sessions: {e}")
                return {}
        return {}
    
    def _save_sessions(self, sessions):
        """Save sessions to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    def create_session(self, user_id):
        """Create new session for user"""
        try:
            sessions = self._load_sessions()
            
            session_data = {
                'user_id': user_id,
                'form_data': {},  # Will store data for each section
                'current_section': None,
                'temp_data': {},  # Temporary data during input
                'photos': [],  # Evidence photos info
                'evidence_folder_id': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'status': 'active'
            }
            
            sessions[str(user_id)] = session_data
            self._save_sessions(sessions)
            
            logger.info(f"Session created for user {user_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            return None
        
    def delete_report_folders(self, user_id):
        """Delete all report folders for a user"""
        try:
            session = self.get_session(user_id)
            if not session:
                return False
                
            folder_ids = [
                session.get('evidence_folder_id'),
                session.get('ba_form_folder_id'),
                session.get('report_folder_id')
            ]
            
            # Hapus session terlebih dahulu
            self.delete_session(user_id)
            
            # Kembalikan folder IDs untuk dihapus oleh service lain
            return [fid for fid in folder_ids if fid]
            
        except Exception as e:
            logger.error(f"Error getting folder IDs for deletion: {e}")
            return []
        
    def cleanup_signature_files(self, user_id):
        """Clean up signature files from session"""
        try:
            session = self.get_session(user_id)
            if not session:
                return False
                
            form_data = session.get('form_data', {})
            tanda_tangan = form_data.get('tanda_tangan', {})
            cleaned_files = 0
            
            # Clean up signature files
            for field_name, file_path in tanda_tangan.items():
                if file_path and file_path.startswith('SIGNATURE_IMAGE:'):
                    actual_path = file_path.replace('SIGNATURE_IMAGE:', '')
                    try:
                        if os.path.exists(actual_path):
                            os.remove(actual_path)
                            cleaned_files += 1
                            logger.info(f"🗑️ Cleaned up signature file: {actual_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not clean up signature file {actual_path}: {e}")
            
            # Clear signature data from session
            if cleaned_files > 0:
                self.update_form_section(user_id, 'tanda_tangan', {})
            
            logger.info(f"Cleaned up {cleaned_files} signature files for user {user_id}")
            return cleaned_files > 0
            
        except Exception as e:
            logger.error(f"Error cleaning up signature files: {e}")
            return False
    
    def get_session(self, user_id):
        """Get current session for user"""
        try:
            sessions = self._load_sessions()
            session = sessions.get(str(user_id))
            
            if session:
                # Update last access time
                session['last_accessed'] = datetime.now().isoformat()
                sessions[str(user_id)] = session
                self._save_sessions(sessions)
            
            return session
            
        except Exception as e:
            logger.error(f"Error getting session for user {user_id}: {e}")
            return None
    
    def update_session(self, user_id, update_data):
        """Update session data"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                # Update specific fields
                for key, value in update_data.items():
                    sessions[str(user_id)][key] = value
                
                # Update timestamp
                sessions[str(user_id)]['updated_at'] = datetime.now().isoformat()
                
                self._save_sessions(sessions)
                
                logger.info(f"Session updated for user {user_id}")
                return True
            else:
                logger.error(f"Session not found for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating session for user {user_id}: {e}")
            return False
    
    def update_form_section(self, user_id, section_id, section_data):
        """Update specific form section data"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                # Initialize form_data if not exists
                if 'form_data' not in sessions[str(user_id)]:
                    sessions[str(user_id)]['form_data'] = {}
                
                # Update section data
                sessions[str(user_id)]['form_data'][section_id] = section_data
                sessions[str(user_id)]['updated_at'] = datetime.now().isoformat()
                
                self._save_sessions(sessions)
                
                logger.info(f"Section '{section_id}' updated for user {user_id}")
                return True
            else:
                logger.error(f"Session not found for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating form section for user {user_id}: {e}")
            return False
    
    def get_form_section(self, user_id, section_id):
        """Get specific form section data"""
        try:
            session = self.get_session(user_id)
            if session and 'form_data' in session:
                return session['form_data'].get(section_id, {})
            return {}
            
        except Exception as e:
            logger.error(f"Error getting form section for user {user_id}: {e}")
            return {}
    
    def add_photo(self, user_id, photo_info):
        """Add photo info to session"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                if 'photos' not in sessions[str(user_id)]:
                    sessions[str(user_id)]['photos'] = []
                
                # Add photo info
                photo_data = {
                    'filename': photo_info.get('filename'),
                    'file_id': photo_info.get('file_id'),
                    'description': photo_info.get('description', ''),
                    'uploaded_at': datetime.now().isoformat()
                }
                
                sessions[str(user_id)]['photos'].append(photo_data)
                sessions[str(user_id)]['updated_at'] = datetime.now().isoformat()
                
                self._save_sessions(sessions)
                
                logger.info(f"Photo added to session for user {user_id}")
                return True
            else:
                logger.error(f"Session not found for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding photo for user {user_id}: {e}")
            return False
    
    def get_photos(self, user_id):
        """Get all photos for user"""
        try:
            session = self.get_session(user_id)
            if session:
                return session.get('photos', [])
            return []
            
        except Exception as e:
            logger.error(f"Error getting photos for user {user_id}: {e}")
            return []
    
    def clear_photos(self, user_id):
        """Clear all photos from session"""
        try:
            return self.update_session(user_id, {'photos': []})
            
        except Exception as e:
            logger.error(f"Error clearing photos for user {user_id}: {e}")
            return False
    
    def set_temp_data(self, user_id, key, value):
        """Set temporary data during input process"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                if 'temp_data' not in sessions[str(user_id)]:
                    sessions[str(user_id)]['temp_data'] = {}
                
                sessions[str(user_id)]['temp_data'][key] = value
                sessions[str(user_id)]['updated_at'] = datetime.now().isoformat()
                
                self._save_sessions(sessions)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error setting temp data for user {user_id}: {e}")
            return False
    
    def get_temp_data(self, user_id, key, default=None):
        """Get temporary data"""
        try:
            session = self.get_session(user_id)
            if session and 'temp_data' in session:
                return session['temp_data'].get(key, default)
            return default
            
        except Exception as e:
            logger.error(f"Error getting temp data for user {user_id}: {e}")
            return default
    
    def clear_temp_data(self, user_id, key=None):
        """Clear temporary data (specific key or all)"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                if key:
                    # Clear specific key
                    if 'temp_data' in sessions[str(user_id)] and key in sessions[str(user_id)]['temp_data']:
                        del sessions[str(user_id)]['temp_data'][key]
                else:
                    # Clear all temp data
                    sessions[str(user_id)]['temp_data'] = {}
                
                sessions[str(user_id)]['updated_at'] = datetime.now().isoformat()
                self._save_sessions(sessions)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error clearing temp data for user {user_id}: {e}")
            return False
    
    def get_session_summary(self, user_id):
        """Get summary of current session progress"""
        try:
            session = self.get_session(user_id)
            if not session:
                return None
            
            form_data = session.get('form_data', {})
            
            summary = {
                'user_id': user_id,
                'created_at': session.get('created_at'),
                'updated_at': session.get('updated_at'),
                'total_sections': 0,
                'completed_sections': 0,
                'sections_status': {},
                'photos_count': len(session.get('photos', [])),
                'has_evidence_folder': bool(session.get('evidence_folder_id'))
            }
            
            # Count completed sections
            for section_id, section_data in form_data.items():
                summary['total_sections'] += 1
                
                # Check if section has any filled data
                has_data = any(
                    str(value).strip() for value in section_data.values() 
                    if value is not None
                )
                
                if has_data:
                    summary['completed_sections'] += 1
                
                summary['sections_status'][section_id] = has_data
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting session summary for user {user_id}: {e}")
            return None
    
    def end_session(self, user_id):
        """End current session"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                # Mark session as completed instead of deleting
                sessions[str(user_id)]['status'] = 'completed'
                sessions[str(user_id)]['completed_at'] = datetime.now().isoformat()
                
                self._save_sessions(sessions)
                
                logger.info(f"Session ended for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error ending session for user {user_id}: {e}")
            return False
    
    def delete_session(self, user_id):
        """Delete session completely"""
        try:
            sessions = self._load_sessions()
            
            if str(user_id) in sessions:
                del sessions[str(user_id)]
                self._save_sessions(sessions)
                
                logger.info(f"Session deleted for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session for user {user_id}: {e}")
            return False
    
    def cleanup_old_sessions(self, days_old=7):
        """Clean up old sessions older than specified days"""
        try:
            sessions = self._load_sessions()
            current_time = datetime.now()
            
            sessions_to_delete = []
            
            for user_id, session_data in sessions.items():
                try:
                    # Check last update time
                    updated_at = datetime.fromisoformat(session_data.get('updated_at', ''))
                    days_diff = (current_time - updated_at).days
                    
                    if days_diff > days_old:
                        sessions_to_delete.append(user_id)
                        
                except Exception as e:
                    logger.warning(f"Error checking session age for user {user_id}: {e}")
            
            # Delete old sessions
            for user_id in sessions_to_delete:
                del sessions[user_id]
                logger.info(f"Cleaned up old session for user {user_id}")
            
            if sessions_to_delete:
                self._save_sessions(sessions)
                logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")
            
            return len(sessions_to_delete)
            
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")
            return 0
    
    def get_all_sessions_stats(self):
        """Get statistics about all sessions"""
        try:
            sessions = self._load_sessions()
            
            stats = {
                'total_sessions': len(sessions),
                'active_sessions': 0,
                'completed_sessions': 0,
                'total_form_sections': 0,
                'total_photos': 0
            }
            
            for session_data in sessions.values():
                status = session_data.get('status', 'active')
                
                if status == 'active':
                    stats['active_sessions'] += 1
                elif status == 'completed':
                    stats['completed_sessions'] += 1
                
                # Count form sections
                form_data = session_data.get('form_data', {})
                stats['total_form_sections'] += len(form_data)
                
                # Count photos
                photos = session_data.get('photos', [])
                stats['total_photos'] += len(photos)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting sessions stats: {e}")
            return None