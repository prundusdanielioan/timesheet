import os
import requests
import base64

class AzureDevOpsService:
    def __init__(self, organization, project, pat_token):
        self.organization = organization
        self.project = project
        self.pat_token = pat_token
        self.base_url = f"https://dev.azure.com/{organization}/{project}/_apis"
        
        # Setup headers with Base64 encoded PAT
        credentials = f":{self.pat_token}"
        base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {base64_credentials}',
            'Content-Type': 'application/json'
        }

    def test_connection(self):
        """Simple test to check if the connection works by fetching project details."""
        url = f"{self.base_url}?api-version=7.1"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Connection failed: {e}")
            if e.response is not None:
                print(f"Response: {e.response.text}")
            return False

    def get_my_active_tasks(self, email):
        """Query Azure DevOps for active Work Items assigned to the user."""
        url = f"{self.base_url}/wit/wiql?api-version=7.1"
        
        # WIQL (Work Item Query Language)
        # We look for anything assigned to you that is NOT closed or removed
        query_body = {
            "query": f"""
                Select [System.Id], [System.Title], [System.State], [System.WorkItemType]
                From WorkItems 
                Where [System.AssignedTo] = '{email}' 
                And [System.State] NOT IN ('Closed', 'Done', 'Resolved', 'Removed')
            """
        }
        
        response = requests.post(url, headers=self.headers, json=query_body)
        response.raise_for_status()
        
        work_items_info = response.json().get('workItems', [])
        
        if not work_items_info:
            return []
            
        # Extract IDs
        ids = [str(item['id']) for item in work_items_info]
        
        # Now fetch the actual details (Titles, etc.) using the IDs
        return self.get_work_items_details(ids)

    def get_work_items_details(self, ids):
        if not ids:
            return []
            
        ids_str = ",".join(ids)
        url = f"{self.base_url}/wit/workitems?ids={ids_str}&api-version=7.1"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json().get('value', [])
