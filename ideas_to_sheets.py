import os
import json
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.sheets.v4 import service as sheets_service
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Sheets configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# Sheet names
CONVERSATION_SHEET = "Conversations"
PODCAST_SHEET = "Podcasts"

def get_sheets_service():
    """Initialize Google Sheets service."""
    try:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = sheets_service.build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Error initializing Google Sheets: {e}")
        return None

def get_existing_titles(service, spreadsheet_id, sheet_name):
    """Get all existing titles from the sheet to avoid duplicates."""
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A2:A")
            .execute()
        )
        values = result.get("values", [])
        return [row[0] for row in values if row]
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch existing titles: {e}")
        return []

def format_characters(characters):
    """Format character list into a readable string."""
    return "; ".join([
        f"{char.get('name', 'Unknown')} ({char.get('role', 'N/A')})"
        for char in characters
    ])

def append_conversation_ideas(service, spreadsheet_id, ideas_data):
    """Append conversation ideas to Google Sheets (one idea per row)."""
    if not service or not ideas_data:
        print("❌ Cannot append ideas: Missing service or data")
        return

    try:
        existing_titles = get_existing_titles(service, spreadsheet_id, CONVERSATION_SHEET)
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        skipped = 0
        synced = 0
        
        metadata = ideas_data.get("metadata", {})
        ideas = ideas_data.get("ideas", [])
        
        for idea in ideas:
            title = idea.get("title", "")
            
            # Skip if title already exists
            if title in existing_titles:
                print(f"⏭️ Skipping duplicate: {title}")
                skipped += 1
                continue
            
            row = [
                title,
                idea.get("description", ""),
                format_characters(idea.get("characters", [])),
                metadata.get("language", ""),
                metadata.get("tone", ""),
                metadata.get("length", ""),
                json.dumps(idea.get("characters", [])),
                current_date,
            ]
            
            body = {"values": [row]}
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{CONVERSATION_SHEET}!A2",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
            synced += 1
        
        if synced > 0:
            print(f"✅ Added {synced} conversation ideas (skipped {skipped} duplicates)")
        else:
            print(f"⏭️ No new ideas to add (all {skipped} were duplicates)")
            
    except Exception as e:
        print(f"❌ Error appending conversation ideas: {e}")

def append_podcast_ideas(service, spreadsheet_id, ideas_data):
    """Append podcast ideas to Google Sheets (one idea per row)."""
    if not service or not ideas_data:
        print("❌ Cannot append ideas: Missing service or data")
        return

    try:
        existing_titles = get_existing_titles(service, spreadsheet_id, PODCAST_SHEET)
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        skipped = 0
        synced = 0
        
        metadata = ideas_data.get("metadata", {})
        ideas = ideas_data.get("podcast_ideas", [])
        
        for idea in ideas:
            title = idea.get("title", "")
            
            # Skip if title already exists
            if title in existing_titles:
                print(f"⏭️ Skipping duplicate: {title}")
                skipped += 1
                continue
            
            row = [
                title,
                idea.get("concept", ""),
                format_characters(idea.get("characters", [])),
                metadata.get("target_audience", ""),
                metadata.get("duration", ""),
                metadata.get("format", ""),
                json.dumps(idea.get("characters", [])),
                current_date,
            ]
            
            body = {"values": [row]}
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{PODCAST_SHEET}!A2",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
            synced += 1
        
        if synced > 0:
            print(f"✅ Added {synced} podcast ideas (skipped {skipped} duplicates)")
        else:
            print(f"⏭️ No new ideas to add (all {skipped} were duplicates)")
            
    except Exception as e:
        print(f"❌ Error appending podcast ideas: {e}")

def ensure_sheet_headers(service, spreadsheet_id):
    """Ensure sheet headers exist."""
    try:
        # Conversation sheet headers
        conv_headers = [
            ["Title", "Description", "Characters", "Language", "Tone", "Length", "Character Data (JSON)"]
        ]
        
        # Podcast sheet headers
        podcast_headers = [
            ["Title", "Concept", "Characters", "Target Audience", "Duration", "Format", "Character Data (JSON)"]
        ]
        
        # Check if sheets exist and create if needed
        sheets_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        
        existing_sheets = {sheet["properties"]["title"] for sheet in sheets_metadata.get("sheets", [])}
        
        # Create conversation sheet if it doesn't exist
        if CONVERSATION_SHEET not in existing_sheets:
            batch_update_body = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {"title": CONVERSATION_SHEET}
                        }
                    }
                ]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=batch_update_body
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{CONVERSATION_SHEET}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": conv_headers},
            ).execute()
            print(f"✅ Created '{CONVERSATION_SHEET}' sheet with headers")
        
        # Create podcast sheet if it doesn't exist
        if PODCAST_SHEET not in existing_sheets:
            batch_update_body = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {"title": PODCAST_SHEET}
                        }
                    }
                ]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=batch_update_body
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{PODCAST_SHEET}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": podcast_headers},
            ).execute()
            print(f"✅ Created '{PODCAST_SHEET}' sheet with headers")
            
    except Exception as e:
        print(f"⚠️ Warning: Error ensuring sheet headers: {e}")

def main():
    if not SPREADSHEET_ID:
        print("❌ Error: GOOGLE_SHEETS_ID not set in .env file")
        return
    
    service = get_sheets_service()
    if not service:
        return
    
    # Ensure sheets and headers exist
    ensure_sheet_headers(service, SPREADSHEET_ID)
    
    # Load and process conversation ideas
    if os.path.exists("ideas.json"):
        try:
            with open("ideas.json", "r", encoding="utf-8") as f:
                conv_data = json.load(f)
            append_conversation_ideas(service, SPREADSHEET_ID, conv_data)
        except Exception as e:
            print(f"❌ Error processing ideas.json: {e}")
    else:
        print("⚠️ ideas.json not found")
    
    # Load and process podcast ideas
    if os.path.exists("podcast_ideas.json"):
        try:
            with open("podcast_ideas.json", "r", encoding="utf-8") as f:
                podcast_data = json.load(f)
            append_podcast_ideas(service, SPREADSHEET_ID, podcast_data)
        except Exception as e:
            print(f"❌ Error processing podcast_ideas.json: {e}")
    else:
        print("⚠️ podcast_ideas.json not found")
    
    print("🎉 Sync to Google Sheets completed!")

if __name__ == "__main__":
    main()
