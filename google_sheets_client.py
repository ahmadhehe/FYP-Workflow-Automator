"""
Google Sheets Client - OAuth2 authentication and Google Sheets API integration
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Scopes required for full Sheets CRUD
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# Default file paths
DEFAULT_TOKEN_PATH = Path("google_tokens.json")
DEFAULT_CREDENTIALS_PATH = Path("client_secret.json")


class GoogleSheetsClient:
    """Client for Google Sheets API with OAuth2 authentication"""

    def __init__(
        self,
        token_path: str = None,
        credentials_path: str = None,
        redirect_uri: str = "http://localhost:8000/auth/google/callback"
    ):
        self.token_path = Path(token_path) if token_path else DEFAULT_TOKEN_PATH
        self.credentials_path = Path(credentials_path) if credentials_path else DEFAULT_CREDENTIALS_PATH
        self.redirect_uri = redirect_uri
        self.creds: Optional[Credentials] = None
        self._sheets_service = None

        # Load existing tokens if available
        self._load_tokens()

    def _load_tokens(self):
        """Load saved OAuth tokens from disk"""
        if self.token_path.exists():
            try:
                self.creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
            except Exception as e:
                print(f"[GoogleSheets] Failed to load tokens: {e}")
                self.creds = None

    def _save_tokens(self):
        """Save OAuth tokens to disk"""
        if self.creds:
            with open(self.token_path, 'w') as f:
                f.write(self.creds.to_json())

    def _get_service(self):
        """Get or create the Sheets API service"""
        self.refresh_if_needed()
        if not self.creds or not self.creds.valid:
            raise Exception("Not authenticated with Google. Please connect your Google account in Settings.")
        if not self._sheets_service:
            self._sheets_service = build('sheets', 'v4', credentials=self.creds)
        return self._sheets_service

    # ========================================================================
    # Authentication
    # ========================================================================

    def is_authenticated(self) -> bool:
        """Check if we have valid (or refreshable) credentials"""
        if not self.creds:
            return False
        if self.creds.valid:
            return True
        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_tokens()
                return True
            except Exception:
                return False
        return False

    def credentials_file_exists(self) -> bool:
        """Check if the client_secret.json file exists"""
        return self.credentials_path.exists()

    def get_auth_url(self) -> str:
        """Generate the Google OAuth consent URL"""
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found at '{self.credentials_path}'. "
                "Please place your Google Cloud client_secret.json in the project root."
            )

        flow = Flow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )

        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to always get refresh token
        )

        return auth_url

    def handle_callback(self, code: str) -> dict:
        """Exchange authorization code for tokens"""
        if not self.credentials_path.exists():
            raise FileNotFoundError("OAuth credentials file not found")

        flow = Flow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )

        flow.fetch_token(code=code)
        self.creds = flow.credentials
        self._sheets_service = None  # Reset service to use new creds
        self._save_tokens()

        # Get user email
        email = self._get_user_email()
        return {"success": True, "email": email}

    def refresh_if_needed(self):
        """Refresh access token if expired"""
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_tokens()
                self._sheets_service = None  # Reset service
            except Exception as e:
                print(f"[GoogleSheets] Token refresh failed: {e}")
                self.creds = None
                self._sheets_service = None

    def _get_user_email(self) -> Optional[str]:
        """Get the email of the authenticated user"""
        try:
            from googleapiclient.discovery import build as build_service
            service = build_service('oauth2', 'v2', credentials=self.creds)
            user_info = service.userinfo().get().execute()
            return user_info.get('email')
        except Exception:
            return None

    def get_status(self) -> dict:
        """Get current authentication status"""
        connected = self.is_authenticated()
        email = None
        if connected:
            email = self._get_user_email()
        return {
            "connected": connected,
            "email": email,
            "credentials_file_exists": self.credentials_file_exists()
        }

    def disconnect(self):
        """Revoke tokens and delete stored credentials"""
        if self.creds:
            try:
                # Attempt to revoke the token
                import requests
                requests.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': self.creds.token},
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
            except Exception:
                pass  # Best effort revocation

        self.creds = None
        self._sheets_service = None

        if self.token_path.exists():
            self.token_path.unlink()

        return {"success": True, "message": "Google account disconnected"}

    # ========================================================================
    # Spreadsheet Operations
    # ========================================================================

    def read_spreadsheet(self, spreadsheet_id: str, range: str) -> dict:
        """
        Read values from a spreadsheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet (from the URL)
            range: A1 notation range, e.g. "Sheet1!A1:D10"
            
        Returns:
            Dict with 'values' (2D array) and metadata
        """
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range
            ).execute()

            values = result.get('values', [])
            return {
                'success': True,
                'range': result.get('range', range),
                'values': values,
                'rows': len(values),
                'cols': max(len(row) for row in values) if values else 0
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def write_spreadsheet(self, spreadsheet_id: str, range: str, values: List[List]) -> dict:
        """
        Write values to a spreadsheet (overwrites existing data in range).
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range: A1 notation range, e.g. "Sheet1!A1:D10"
            values: 2D array of values to write
            
        Returns:
            Dict with update result
        """
        try:
            service = self._get_service()
            body = {'values': values}
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return {
                'success': True,
                'updated_range': result.get('updatedRange', ''),
                'updated_rows': result.get('updatedRows', 0),
                'updated_columns': result.get('updatedColumns', 0),
                'updated_cells': result.get('updatedCells', 0)
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def append_rows(self, spreadsheet_id: str, range: str, values: List[List]) -> dict:
        """
        Append rows to a spreadsheet (adds after existing data).
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            range: A1 notation range to append after, e.g. "Sheet1!A:D"
            values: 2D array of rows to append
            
        Returns:
            Dict with append result
        """
        try:
            service = self._get_service()
            body = {'values': values}
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            updates = result.get('updates', {})
            return {
                'success': True,
                'updated_range': updates.get('updatedRange', ''),
                'updated_rows': updates.get('updatedRows', 0),
                'updated_cells': updates.get('updatedCells', 0)
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_spreadsheet(self, title: str, sheet_names: List[str] = None) -> dict:
        """
        Create a new Google Spreadsheet.
        
        Args:
            title: Title of the spreadsheet
            sheet_names: Optional list of sheet tab names (defaults to ["Sheet1"])
            
        Returns:
            Dict with spreadsheet ID and URL
        """
        try:
            service = self._get_service()

            sheets = []
            if sheet_names:
                for i, name in enumerate(sheet_names):
                    sheets.append({
                        'properties': {
                            'title': name,
                            'index': i
                        }
                    })
            else:
                sheets.append({
                    'properties': {
                        'title': 'Sheet1',
                        'index': 0
                    }
                })

            spreadsheet_body = {
                'properties': {'title': title},
                'sheets': sheets
            }

            result = service.spreadsheets().create(body=spreadsheet_body).execute()

            spreadsheet_id = result['spreadsheetId']
            return {
                'success': True,
                'spreadsheet_id': spreadsheet_id,
                'url': f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
                'title': title,
                'sheets': [s['properties']['title'] for s in result.get('sheets', [])]
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_sheets_list(self, spreadsheet_id: str) -> dict:
        """
        Get all sheet tabs in a spreadsheet.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            
        Returns:
            Dict with list of sheet names and properties
        """
        try:
            service = self._get_service()
            result = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields='properties.title,sheets.properties'
            ).execute()

            sheets = []
            for sheet in result.get('sheets', []):
                props = sheet.get('properties', {})
                sheets.append({
                    'title': props.get('title', ''),
                    'index': props.get('index', 0),
                    'sheetId': props.get('sheetId', 0),
                    'rowCount': props.get('gridProperties', {}).get('rowCount', 0),
                    'columnCount': props.get('gridProperties', {}).get('columnCount', 0)
                })

            return {
                'success': True,
                'spreadsheet_title': result.get('properties', {}).get('title', ''),
                'sheets': sheets,
                'sheet_count': len(sheets)
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def format_cells(self, spreadsheet_id: str, requests: List[Dict]) -> dict:
        """
        Apply formatting to cells using batchUpdate.
        
        Args:
            spreadsheet_id: The ID of the spreadsheet
            requests: List of formatting request objects (Google Sheets API format)
                      e.g. [{"repeatCell": {"range": {...}, "cell": {...}, "fields": "..."}}]
            
        Returns:
            Dict with batch update result
        """
        try:
            service = self._get_service()
            body = {'requests': requests}
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()

            return {
                'success': True,
                'replies_count': len(result.get('replies', [])),
                'spreadsheet_id': result.get('spreadsheetId', spreadsheet_id)
            }
        except HttpError as e:
            return {'success': False, 'error': f"Google Sheets API error: {e.reason}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
