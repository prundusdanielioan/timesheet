import subprocess

def send_via_local_outlook(recipient_emails, subject, body, file_path):
    escaped_subject = subject.replace('\\', '\\\\').replace('"', '\\"')
    escaped_body = body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\r')
    
    emails = [e.strip() for e in recipient_emails.split(",") if e.strip()]
    recipients_applescript = ""
    for email in emails:
        recipients_applescript += f'make new recipient at newMail with properties {{email address:{{address:"{email}"}}}}\n'
        
    applescript = f'''
    tell application "Microsoft Outlook"
        set newMail to make new outgoing message with properties {{subject:"{escaped_subject}"}}
        set content of newMail to "{escaped_body}"
        {recipients_applescript}
        make new attachment at newMail with properties {{file:POSIX file "{file_path}"}}
        send newMail
    end tell
    '''
    
    process = subprocess.Popen(
        ['osascript', '-e', applescript],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))
