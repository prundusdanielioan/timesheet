import os
from dotenv import load_dotenv
from azure_service import AzureDevOpsService

load_dotenv()

ORGANIZATION = os.getenv("AZURE_ORGANIZATION")
PROJECT = os.getenv("AZURE_PROJECT")
PAT_TOKEN = os.getenv("AZURE_PAT_TOKEN")
EMAIL = os.getenv("AZURE_EMAIL")

def main():
    if not PAT_TOKEN or PAT_TOKEN == "your_pat_token_here":
        print("Error: AZURE_PAT_TOKEN not found or not set properly in .env file.")
        return

    print(f"--- Initializing Azure DevOps Service for '{ORGANIZATION}/{PROJECT}' ---")
    azure_service = AzureDevOpsService(organization=ORGANIZATION, project=PROJECT, pat_token=PAT_TOKEN)

    print(f"\nFetching Active Work Items for {EMAIL}...")
    try:
        items = azure_service.get_my_active_tasks(EMAIL)
        
        if not items:
            print("No active items found.")
        else:
            print(f"\n✅ Found {len(items)} active items:")
            print("-" * 50)
            for index, item in enumerate(items, 1):
                fields = item.get('fields', {})
                item_id = item.get('id')
                title = fields.get('System.Title', 'No Title')
                state = fields.get('System.State', 'Unknown')
                print(f"{index}. [#{item_id}] {title} (State: {state})")
            print("-" * 50)
            combined_names = ", ".join([f"{item.get('fields', {}).get('System.Title')}" for item in items])
            print(f"\nTimesheet summary string for today:\n{combined_names}")
    except Exception as e:
        print(f"❌ Error fetching work items: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Details: {e.response.text}")

if __name__ == "__main__":
    main()
