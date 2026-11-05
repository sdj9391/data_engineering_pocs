"""Regenerates synthetic CSV data and sample tickets for manual reference.
Ticket dates are relative to today.  Run from the project root:  python scripts/generate_data.py
"""
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
now = datetime.now(timezone.utc).replace(microsecond=0)

N, A, H, S = "Network Operations", "Identity & Access Management", "Desktop & Hardware Support", "Application Support"

teams = [
    ("network", N, "network-ops@example.com"),
    ("access", A, "iam-support@example.com"),
    ("hardware", H, "hardware-support@example.com"),
    ("software", S, "app-support@example.com"),
]

faq = [
    ("KB01", "VPN will not connect", "network", "vpn,connect,remote,tunnel,timeout,times out",
     "1) Check your internet works. 2) Quit and restart the VPN client. 3) Switch networks (for example a phone hotspot). 4) If it still fails, note the error code and contact Network Operations."),
    ("KB02", "Wi-Fi keeps dropping", "network", "wifi,wi-fi,wireless,drops,disconnect,intermittent",
     "1) Forget the Wi-Fi network and rejoin. 2) Move closer to an access point. 3) Restart the laptop Wi-Fi adapter. 4) Report the location and time if it keeps happening."),
    ("KB03", "Internet or network is slow", "network", "slow,internet,latency,speed,bandwidth,download",
     "1) Run a speed test and note the result. 2) Close streaming and large downloads. 3) Try a wired connection. 4) Report the location if the speed stays low."),
    ("KB04", "Reset your password", "access", "password,reset,expired,forgot,change",
     "1) Open the self-service password portal. 2) Verify with MFA. 3) Choose a new password (12+ characters). 4) Sign in again on all devices."),
    ("KB05", "Account locked after failed sign-ins", "access", "locked,lockout,locked out,too many attempts,unlock,account",
     "Accounts unlock automatically after 30 minutes. For immediate unlock use the self-service portal with MFA, or contact IAM."),
    ("KB06", "Set up MFA on a new phone", "access", "mfa,2fa,authenticator,verification code,new phone,codes",
     "1) Install the authenticator app on the new phone. 2) Use the MFA re-enrolment page while signed in on a trusted device. 3) Scan the new QR code. 4) Remove the old device."),
    ("KB07", "Request access to a shared folder or application", "access", "permission,access request,shared drive,folder,denied,sharepoint",
     "Submit an access request in the service portal with the resource name and your manager as approver. Typical approval takes 1 to 2 working days."),
    ("KB08", "Laptop will not power on", "hardware", "power,battery,charger,boot,won't turn on,black screen,turn on",
     "1) Try a different power outlet and charger. 2) Hold the power button for 15 seconds, then retry. 3) Remove docks and USB devices. 4) If still dead, book a hardware check."),
    ("KB09", "External monitor not detected", "hardware", "monitor,display,hdmi,docking,dock,second screen,detected",
     "1) Reseat the HDMI/USB-C cable. 2) Press Win+P (Windows) or open Display settings (Mac) and click Detect displays. 3) Try another cable or port. 4) Restart the laptop with the dock connected."),
    ("KB10", "Printer offline or not printing", "hardware", "printer,print,offline,queue,toner,jam",
     "1) Check the printer is on and shows no error. 2) Clear the print queue. 3) Remove and re-add the printer. 4) Report the printer asset tag if it stays offline."),
    ("KB11", "Install approved software", "software", "install,software,application,license,download",
     "Open the company software portal, pick the approved application and click Install. If it is not listed, raise a request with a business justification."),
    ("KB12", "Outlook or email not syncing", "software", "outlook,email,sync,mailbox,calendar,not receiving",
     "1) Check you are online. 2) Restart Outlook. 3) Remove and re-add the account profile. 4) Check mailbox storage is not full."),
    ("KB13", "No audio or video in Teams or Zoom", "software", "teams,zoom,microphone,camera,audio,meeting,sound",
     "1) Check the correct microphone/camera is selected in the app settings. 2) Allow the app in OS privacy settings. 3) Restart the app. 4) Test with another device."),
    ("KB14", "Application crashes or freezes", "software", "crash,freeze,frozen,not responding,hang,error",
     "1) Save work and restart the app. 2) Install pending updates. 3) Restart the laptop. 4) If it repeats, note the steps and the error message and raise a ticket."),
]

# (subject, description, category, priority, status, days_ago, resolution_hours, team)
past = [
    ("VPN disconnects every 10 minutes", "VPN session drops repeatedly while working from home. Reconnecting works but it happens again soon.", "network", "medium", "resolved", 85, 10.5, N),
    ("Office Wi-Fi extremely slow on 3rd floor", "Wi-Fi speeds are very slow in the 3rd floor meeting rooms since Monday.", "network", "medium", "resolved", 78, 16.0, N),
    ("Complete internet outage in Riyadh office", "No internet access for the entire office, the network is down for all users.", "network", "high", "resolved", 70, 3.0, N),
    ("Cannot reach internal wiki", "Internal wiki times out from the office network while other sites work fine.", "network", "medium", "resolved", 64, 12.0, N),
    ("Request network port for desk 14B", "Please enable the ethernet port at my new desk, there is no connectivity at the moment.", "network", "medium", "resolved", 60, 30.0, N),
    ("VPN client error 809", "VPN shows error 809 when connecting from hotel Wi-Fi.", "network", "medium", "resolved", 55, 8.0, N),
    ("DNS resolution failing for intranet", "Intranet hostnames are not resolving for several teams, ping by IP works.", "network", "high", "resolved", 48, 2.5, N),
    ("Slow file downloads from shared server", "Large downloads from the file server crawl at very low speed.", "network", "medium", "resolved", 40, 20.0, N),
    ("Guest Wi-Fi not accessible", "Visitors cannot connect to the guest Wi-Fi network in reception.", "network", "medium", "open", 3, None, N),
    ("Intermittent network drops on docking station", "Wired connection through the dock drops several times a day.", "network", "medium", "in_progress", 6, None, N),

    ("Password expired, cannot log in", "My password expired and the reset page shows an error.", "access", "high", "resolved", 88, 1.5, A),
    ("Account locked after failed attempts", "Account locked after too many attempts on the finance portal.", "access", "high", "resolved", 80, 1.0, A),
    ("MFA codes not working on new phone", "Authenticator codes are rejected after I moved to a new phone.", "access", "medium", "resolved", 75, 6.0, A),
    ("Need access to Marketing shared drive", "Please grant me read access to the Marketing shared drive for the campaign project.", "access", "low", "resolved", 66, 30.0, A),
    ("Permission denied on SharePoint site", "Getting permission denied when opening the Projects SharePoint site.", "access", "medium", "resolved", 58, 18.0, A),
    ("Cannot log in to HR portal", "I can't login to the HR portal, it says invalid credentials.", "access", "high", "resolved", 52, 2.0, A),
    ("New joiner needs accounts created", "New starter on Monday needs email, VPN and ERP accounts.", "access", "medium", "resolved", 45, 22.0, A),
    ("Request admin rights for developer tools", "Need local admin rights to install a container runtime.", "access", "low", "resolved", 38, 48.0, A),
    ("SSO loop when opening CRM", "Single sign-on keeps redirecting back to the login page for the CRM.", "access", "medium", "open", 2, None, A),
    ("Reset my password", "Forgot my password and cannot receive the reset email.", "access", "medium", "in_progress", 4, None, A),

    ("Laptop will not power on", "Laptop does not turn on, charger light is blinking.", "hardware", "low", "resolved", 86, 36.0, H),
    ("External monitor not detected via dock", "Second monitor is not detected when connected to the docking station.", "hardware", "low", "resolved", 79, 24.0, H),
    ("Printer on floor 2 offline", "The floor 2 shared printer shows offline for everyone.", "hardware", "medium", "resolved", 72, 6.0, H),
    ("Keyboard keys sticking", "Several keys on my laptop keyboard are sticking.", "hardware", "low", "resolved", 68, 60.0, H),
    ("Laptop battery drains in 1 hour", "Battery lasts about an hour even after a full charge.", "hardware", "low", "resolved", 61, 72.0, H),
    ("Headset microphone not working", "USB headset microphone is not recognised by the laptop.", "hardware", "low", "resolved", 54, 20.0, H),
    ("Laptop screen cracked", "Dropped my laptop and the screen is cracked, need a replacement.", "hardware", "medium", "resolved", 47, 48.0, H),
    ("Mouse pointer freezing", "Wireless mouse pointer keeps freezing for a few seconds.", "hardware", "low", "resolved", 36, 28.0, H),
    ("Request second monitor", "Please provide a second monitor for my desk.", "hardware", "low", "open", 5, None, H),
    ("Docking station has no power light", "Docking station shows no power light.", "hardware", "low", "in_progress", 7, None, H),

    ("Outlook not syncing", "Outlook stopped syncing email since the weekend.", "software", "low", "resolved", 90, 12.0, S),
    ("Teams meeting has no audio", "No audio in Teams meetings although the microphone works elsewhere.", "software", "medium", "resolved", 83, 5.0, S),
    ("Excel crashes when opening large file", "Excel crashes every time I open the quarterly forecast workbook.", "software", "medium", "resolved", 76, 26.0, S),
    ("Install approved PDF editor", "Please install the approved PDF editor, the license is already approved.", "software", "low", "resolved", 69, 44.0, S),
    ("ERP error when saving invoices", "ERP shows error 500 when saving invoices, production invoicing is blocked.", "software", "high", "resolved", 62, 4.0, S),
    ("Browser extension blocked", "Company browser policy blocks an extension I need.", "software", "low", "resolved", 57, 50.0, S),
    ("Zoom camera not detected", "Zoom cannot find the camera.", "software", "low", "resolved", 50, 10.0, S),
    ("Windows update stuck at 30%", "Windows update has been at 30% for hours.", "software", "low", "resolved", 43, 30.0, S),
    ("CRM freezing during reports", "CRM freezes when running the monthly report.", "software", "medium", "open", 1, None, S),
    ("Need license for design tool", "Request a license for the design tool for a new project.", "software", "low", "in_progress", 8, None, S),
]

# Sample tickets for manual reference; these are not stored in the database.
sample_tickets = [
    ("T01", "VPN not connecting from home", "Since this morning the VPN client times out when I try to connect from home. I restarted the VPN client twice. Internet works fine otherwise."),
    ("T02", "Cannot login to HR portal", "I can't login to the HR portal. It says my password is incorrect even after I reset it."),
    ("T03", "Whole office has no internet", "The entire office lost its internet connection. The network is down for everyone on the 2nd floor."),
    ("T04", "Laptop will not start", "My laptop won't turn on. The charger light blinks and the screen stays black."),
    ("T05", "Outlook not syncing", "Outlook email stopped syncing after the update. New messages are not showing up."),
    ("T06", "Something is wrong", "Things have been weird since this morning, can someone take a look?"),
    ("T07", "Parking pass request", "I need a new parking pass for the visitor lot next week."),
    ("T08", "VPN and laptop issues", "My laptop flickers and the VPN keeps disconnecting; not sure which is the real problem."),
    ("T09", "Production acting strange", "Production is acting strange for everyone, not sure what is going on."),
]


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"data/{name}: {len(rows)} rows")


write_csv("teams.csv", ["category", "team_name", "team_email"], teams)
write_csv("faq_articles.csv", ["kb_id", "title", "category", "keywords", "body"], faq)
rows = []
for i, (subj, desc, cat, prio, status, days_ago, hours, team) in enumerate(past, 1):
    submitted = (now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows.append((f"TKT-{i:04d}", subj, desc, cat, prio, status, submitted, "" if hours is None else hours, team))
write_csv("tickets.csv", ["ticket_id", "subject", "description", "category", "priority", "status",
                          "submitted_at", "resolution_hours", "assigned_team"], rows)
(OUT / "sample_tickets.json").write_text(json.dumps(
    [dict(id=i, subject=s, description=d) for i, s, d in sample_tickets], indent=2))
print(f"data/sample_tickets.json: {len(sample_tickets)} sample tickets")
