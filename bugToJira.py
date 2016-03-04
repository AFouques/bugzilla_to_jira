#!/bin/python3

import getpass
import os
from jira import JIRA
import mysql.connector

ANDROID_VERSION_KEY = '[ANDROID_VERSION_KEY]'
DESCRIPTION_KEY = '[DESCRIPTION_KEY]'
JIRA_LABEL = 'From_Bugzilla'

# Functions!

def get_value(question, is_mandatory=False, default_value='', is_password=False):
    """Get a value from the user"""
    value = ''
    is_value_ok = False
    while not is_value_ok:
        if is_password:
            value = getpass.getpass(question)
        else:
            value = input(question)
        
        if value == '' and default_value != '':
            value = default_value
        
        if value == '' and is_mandatory:
            print("This value is mandatory, again...")
        else:
            is_value_ok = True
    return value

# Script!

print("\nWelcome to this awesome script which will migrate your bugzilla tickets to your JIRA instance. please give us all your personnal informations.\n")

# Get Bugzilla DB info and connect
mysql_host = get_value("MySQL host [localhost]: ", default_value='localhost')
mysql_user = get_value("MySQL user [root]: ", default_value='root')
mysql_password = get_value("MySQL password [root]: ", default_value='root', is_password=True)
mysql_database = get_value("MySQL database table [bugzilla]: ", default_value='bugzilla')

print("\nConnecting to your MySQL database...")
mysql_conn = mysql.connector.connect(host=mysql_host, user=mysql_user,password=mysql_password, database=mysql_database)
print("Connected.\n")

# Get JIRA info and connect
jira_username = get_value("JIRA username: ", is_mandatory=True)
jira_password = get_value("JIRA password: ", is_mandatory=True, is_password=True)
jira_instance = get_value("JIRA instance: https://[yourJiraInstance].atlassian.net: ", is_mandatory=True)
jira_project = get_value("JIRA project [TEST]: ", default_value = 'TEST')

print("\nConnecting to your JIRA instance...")
jira_options = {'server': 'https://' + jira_instance + '.atlassian.net'}
jira = JIRA(jira_options, basic_auth=(jira_username, jira_password))
print("Connected.\n")

# Get Zendesk instance to create cool links
zendesk_instance = get_value("Zendesk instance: https://[yourZendeskInstance].zendesk.com: ", is_mandatory=True)

# Load bugs from bugzilla
print("\nLoading bugs...")
cursor_bugs = mysql_conn.cursor()
cursor_bugs.execute("""
SELECT 
b.bug_id,
b.bug_severity,
b.bug_status,
b.creation_ts,
b.short_desc,
b.op_sys,
b.priority,
p.name product,
b.rep_platform,
b.version,
c.name component,
b.cf_bugtype,
b.cf_listusers,
b.cf_zendesk_ticket_id_text

FROM bugs b, products p, components c

WHERE
b.bug_status NOT IN ('RELEASED', 'CLOSED')
AND b.resolution IN ('')
AND b.product_id = p.id
AND b.component_id = c.id

ORDER BY b.bug_id""")
rows_bugs = cursor_bugs.fetchall()

print("Loading android versions...")
cursor_android_version = mysql_conn.cursor()
cursor_android_version.execute("""
SELECT av.bug_id, av.value
FROM bug_cf_android_version av""")
rows_android_version = cursor_android_version.fetchall()

print("Loading attachements...")
cursor_attachements = mysql_conn.cursor()
cursor_attachements.execute("""
SELECT a.bug_id, a.filename, a.description, d.thedata
FROM attachments a, attach_data d
WHERE a.attach_id = d.id
ORDER BY a.bug_id""")
rows_attachements = cursor_attachements.fetchall()

print("Loading comments...")
cursor_comments = mysql_conn.cursor()
cursor_comments.execute("""
SELECT c.bug_id, w.login_name, c.bug_when, c.thetext
FROM longdescs c, profiles w
WHERE c.who = w.userid
ORDER BY c.comment_id""")
rows_comments = cursor_comments.fetchall()

print("\nDisconnecting from your MySQL database...")
mysql_conn.close()
print("Disconnected.\n")

# We will store a dict with bugzilla {bug id: jira issue} to, then, add android versions, comments and attachements
bug_id_jira_issue_dict = {}

# Create JIRA issues from bugs (without comments, attachements and Android versions)
print("Creating JIRA issue for each bug...\n")
for row_bug in rows_bugs:
    print("Loading bug {0} : {1}".format(row_bug[0], row_bug[4]))
    issue_summary = '[BZ' + str(row_bug[0]) + '] ' + row_bug[4]
    issue_description = '[CREATED]: ' + str(row_bug[3]) + '\n' + \
                        '[Operating system]: ' + row_bug[5] + '\n' + \
                        '[Product]: ' + row_bug[7] + '\n' + \
                        '[Platform]: ' + row_bug[8] + '\n' + \
                        '[Version]: ' + row_bug[9] + '\n' + \
                        '[Android Version]: ' + ANDROID_VERSION_KEY + '\n' + \
                        '[Component ID]: ' + row_bug[10] + '\n' + \
                        '[Affected users]: ' + row_bug[12] + '\n' + \
                        '[Zendesk ticket]: https://' + zendesk_instance + '.zendesk.com/agent/tickets/' + row_bug[13] + '\n' + \
                        '[Description]:\n' + DESCRIPTION_KEY
    issue_priority = row_bug[6].replace("Normal", "Medium").replace("---", "Medium")
    issue_dict = {'project':jira_project, 'summary': issue_summary, 'description': issue_description, 'priority': {'name': issue_priority}, "labels": [JIRA_LABEL]}
    issue_type = 'Story'
    if row_bug[11] in ['Ticket', 'Problem']:
        issue_type = 'Bug'
        issue_severity = row_bug[1].replace("---", "normal").replace("-", " ")
        issue_status = row_bug[2].replace("---", "TO_CHECK").replace("-", " ").replace("_", " ").capitalize()
        issue_dict.update({'customfield_10600': {'value': issue_severity}, 'customfield_10601': {'value': issue_status}})
    issue_dict.update({'issuetype': {'name': issue_type}})
    new_issue = jira.create_issue(fields=issue_dict)
    bug_id_jira_issue_dict.update({row_bug[0]: new_issue})
    print("Created JIRA issue https://" + jira_instance + ".atlassian.net/browse/" + new_issue.key + "\n")

# Add Android versions for each issues
print("Adding Android versions to JIRA issues...")
# Create a dict with bug_id | android versions
bug_id_android_versions_dict = {}
# Loop on android versions table to fill the dict
for row_android_version in rows_android_version:
    value = bug_id_android_versions_dict.get(row_android_version[0])
    if value == None:
        bug_id_android_versions_dict.update({row_android_version[0]: row_android_version[1]})
    else:
        bug_id_android_versions_dict.update({row_android_version[0]: value + ", " + row_android_version[1]})
# Loop on each jira issue
for bug in bug_id_jira_issue_dict:
    if bug not in bug_id_android_versions_dict:
        continue
    # Get the description from bug_id_jira_id_dict and update the android version with the one stored in bug_id_android_versions_dict
    issue = bug_id_jira_issue_dict.get(bug)
    description = issue.fields.description
    description = description.replace(ANDROID_VERSION_KEY, bug_id_android_versions_dict.get(bug))
    # push the result on jira
    bug_id_jira_issue_dict.get(bug).update(description= description)
    print("Updated JIRA issue https://" + jira_instance + ".atlassian.net/browse/" + issue.key + "")

# Add Attachements to issues
print("\nAdding attachements to JIRA issues...\n")
# Loop on attachement table
for row_attachement in rows_attachements:
    if row_attachement[0] not in bug_id_jira_issue_dict:
        continue
    issue = bug_id_jira_issue_dict.get(row_attachement[0])
    filename = row_attachement[1]
    description = row_attachement[2]
    file = open('./' + filename, 'wb')
    file.write(row_attachement[3])
    file.close()
    # Reopen the file in 'rb' as JIRA really want that
    file = open('./' + filename, 'rb')
    # Add attachement to jira
    jira.add_attachment(issue, file, filename)
    file.close()
    os.remove('./' + filename)
    comment = "Add an attached file : [^" + filename + "]\n\n" + description
    # Add a comment in jira issue with a description of the attachement
    jira.add_comment(issue, comment)
    print("Added attachement " + filename + " to issue https://" + jira_instance + ".atlassian.net/browse/" + issue.key)

# Add comments to issues
print("\nAdding comments to JIRA issues...\n")
# Create an array to list the issue who already have a description, as the first bugzilla comment will be the JIRA description
issues_with_description = []
# Loop on comments table
for row_comments in rows_comments:
    if row_comments[0] not in bug_id_jira_issue_dict or row_comments[3] == '':
        continue
    issue = bug_id_jira_issue_dict.get(row_comments[0])
    long_comment = str(row_comments[2]) + ", by " + row_comments[1] + ":\n" + row_comments[3]
    if issue.key not in issues_with_description:
        # Get the description from bug_id_jira_id_dict and update the description with the one stored in row_comments
        description = issue.fields.description
        description = description.replace(DESCRIPTION_KEY, long_comment)
        # Push the result on jira
        issue.update(description= description)
        print("Updated JIRA issue description https://" + jira_instance + ".atlassian.net/browse/" + issue.key + "")
        issues_with_description.append(issue.key)
    else:
        # Add the comment as... comment in the issue
        jira.add_comment(issue, long_comment)
        print("Added comment to issue https://" + jira_instance + ".atlassian.net/browse/" + issue.key)

print("\nThat's all folks, keep the vibe and stay true!\nCmoaToto\n")
