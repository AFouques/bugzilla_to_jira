#!/usr/bin/env python3

import getpass
import os
from jira import JIRA
import mysql.connector

ANDROID_VERSION_KEY = '[ANDROID_VERSION_KEY]'
DESCRIPTION_KEY = '[DESCRIPTION_KEY]'
DUPLICATES_USERS_KEY = '[DUPLICATES_USERS_KEY]'
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

print("\nWelcome to this awesome script which will migrate your bugzilla " + \
" tickets to your JIRA instance. please give us all your personnal informations.\n")

# Get Bugzilla DB info and connect
mysql_host = get_value("MySQL host [localhost]: ", default_value='localhost')
mysql_user = get_value("MySQL user [root]: ", default_value='root')
mysql_password = get_value("MySQL password [root]: ", default_value='root', is_password=True)
mysql_database = get_value("MySQL database table [bugzilla]: ", default_value='bugzilla')

print("\nConnecting to your MySQL database...")
mysql_conn = mysql.connector.connect(host=mysql_host,
                                     user=mysql_user,
                                     password=mysql_password,
                                     database=mysql_database)
print("Connected.\n")

# Get JIRA info and connect
jira_username = get_value("JIRA username: ", is_mandatory=True)
jira_password = get_value("JIRA password: ", is_mandatory=True, is_password=True)
jira_instance = get_value("JIRA instance: https://[yourJiraInstance].atlassian.net: ", is_mandatory=True)
jira_project = get_value("JIRA project [TEST]: ", default_value = 'TEST')

print("\nConnecting to your JIRA instance...")
jira_options = {'server': 'https://{}.atlassian.net'.format(jira_instance)}
jira = JIRA(jira_options, basic_auth=(jira_username, jira_password))
print("Connected.\n")

# Get Zendesk instance to create cool links
zendesk_instance = get_value("Zendesk instance: https://[yourZendeskInstance].zendesk.com: ",
                             is_mandatory=True)

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
    AND p.name NOT IN ('Genymotion web site')

    ORDER BY b.bug_id""")
rows_bugs = cursor_bugs.fetchall()

# Load android versions
print("Loading android versions...")
cursor_android_version = mysql_conn.cursor()
cursor_android_version.execute("""
    SELECT av.bug_id, av.value
    FROM bug_cf_android_version av""")
rows_android_version = cursor_android_version.fetchall()

# Load attachments
print("Loading attachments...")
cursor_attachments = mysql_conn.cursor()
cursor_attachments.execute("""
    SELECT a.bug_id, a.filename, a.description, d.thedata
    FROM bugs b, products p, attachments a, attach_data d
    WHERE b.bug_id = a.bug_id
        AND a.attach_id = d.id
        AND b.product_id = p.id
        AND b.bug_status NOT IN ('RELEASED', 'CLOSED')
        AND b.resolution IN ('')
        AND p.name NOT IN ('Genymotion web site')
    ORDER BY a.bug_id""")
rows_attachments = cursor_attachments.fetchall()

# Load comments
print("Loading comments...")
cursor_comments = mysql_conn.cursor()
cursor_comments.execute("""
    SELECT c.bug_id, w.login_name, c.bug_when, c.thetext
    FROM bugs b, products p, longdescs c, profiles w
    WHERE b.bug_id = c.bug_id
        AND c.who = w.userid
        AND b.product_id = p.id
        AND b.bug_status NOT IN ('RELEASED', 'CLOSED')
        AND b.resolution IN ('')
        AND c.thetext NOT IN ('')
        AND p.name NOT IN ('Genymotion web site')
    ORDER BY c.comment_id""")
rows_comments = cursor_comments.fetchall()

# Load listusers from duplicates
print("Loading users from duplicates...")
cursor_dup_users = mysql_conn.cursor()
cursor_dup_users.execute("""
    SELECT b.bug_id original, d.cf_listusers
    FROM bugs d, bugs b, duplicates dup, products p
    WHERE b.bug_id = dup.dupe_of
        AND d.bug_id = dup.dupe
        AND b.product_id = p.id
        AND b.bug_status NOT IN ('RELEASED', 'CLOSED')
        AND b.resolution IN ('')
        AND p.name NOT IN ('Genymotion web site')
    ORDER BY b.bug_id""")
rows_dup_users = cursor_dup_users.fetchall()

# Load attachments from duplicates
print("Loading attachments from duplicates...")
cursor_dup_attachments = mysql_conn.cursor()
cursor_dup_attachments.execute("""
    SELECT b.bug_id original, a.filename, a.description, attach.thedata
    FROM bugs d, bugs b, duplicates dup, products p, attachments a, attach_data attach
    WHERE b.bug_id = dup.dupe_of
        AND d.bug_id = dup.dupe
        AND b.product_id = p.id
        AND a.bug_id = d.bug_id
        AND a.attach_id = attach.id
        AND b.bug_status NOT IN ('RELEASED', 'CLOSED')
        AND b.resolution IN ('')
        AND p.name NOT IN ('Genymotion web site')
    ORDER BY b.bug_id""")
rows_dup_attachments = cursor_dup_attachments.fetchall()

# Load comments from duplicates
print("Loading comments from duplicates...")
cursor_dup_comments = mysql_conn.cursor()
cursor_dup_comments.execute("""
    SELECT b.bug_id original, w.login_name, c.bug_when, c.thetext
    FROM bugs d, bugs b, duplicates dup, longdescs c, profiles w, products p
    WHERE
        c.bug_id = d.bug_id
        AND b.bug_id = dup.dupe_of
        AND d.bug_id = dup.dupe
        AND c.who = w.userid
        AND b.product_id = p.id
        AND b.bug_status NOT IN ('RELEASED', 'CLOSED')
        AND b.resolution IN ('')
        AND c.thetext NOT IN ('')
        AND c.thetext NOT LIKE 'Duplicate%'
        AND p.name NOT IN ('Genymotion web site')
    ORDER BY c.comment_id""")
rows_dup_comments = cursor_dup_comments.fetchall()

print("\nDisconnecting from your MySQL database...")
mysql_conn.close()
print("Disconnected.\n")

# We will store a dict with bugzilla {bug id: jira issue} to, then, add
# android versions, comments and attachments
bug_id_jira_issue_dict = {}

# Create JIRA issues from bugs (without comments, attachments and Android versions)
print("Creating JIRA issue for each bug...\n")
for row_bug in rows_bugs:
    print("Loading bug {0} : {1}".format(row_bug[0], row_bug[4]))
    issue_summary = '[BZ{0[0]}] {0[4]}'.format(row_bug)
    issue_description = """[CREATED]: {0[3]}
[Operating system]: {0[5]}
[Product]: {0[7]}
[Platform]: {0[8]}
[Version]: {0[9]}
[Android Version]: {1}
[Component ID]: {0[10]}
[Affected users]: {0[12]} {2}
[Zendesk ticket]: https://{3}.zendesk.com/agent/tickets/{0[13]}
[Description]:
{4}""".format(row_bug, ANDROID_VERSION_KEY, DUPLICATES_USERS_KEY, zendesk_instance, DESCRIPTION_KEY)
    issue_priority = row_bug[6].replace("Normal", "Medium").replace("---", "Medium")
    issue_dict = {'project':jira_project,
                  'summary': issue_summary,
                  'description': issue_description,
                  'priority': {'name': issue_priority},
                  "labels": [JIRA_LABEL]}
    issue_type = 'Story'
    if row_bug[11] in ['Ticket', 'Problem']:
        issue_type = 'Bug'
        issue_severity = row_bug[1].replace("---", "normal").replace("-", " ")
        issue_status = row_bug[2].replace("---", "TO_CHECK") \
                                 .replace("-", " ") \
                                 .replace("_", " ") \
                                 .capitalize()
        issue_dict.update({'customfield_10600': {'value': issue_severity},
                           'customfield_10601': {'value': issue_status}})
    issue_dict['issuetype'] = {'name': issue_type}
    new_issue = jira.create_issue(fields=issue_dict)
    bug_id_jira_issue_dict[row_bug[0]] = new_issue
    print("Created JIRA issue https://{}.atlassian.net/browse/{}\n" \
          .format(jira_instance, new_issue.key))

# Add Android versions for each issues
print("Adding Android versions to JIRA issues...")
# Create a dict with bug_id | android versions
bug_id_android_versions_dict = {}
# Loop on android versions table to fill the dict
for row_android_version in rows_android_version:
    value = bug_id_android_versions_dict.get(row_android_version[0])
    if value is None:
        bug_id_android_versions_dict[row_android_version[0]] = row_android_version[1]
    else:
        bug_id_android_versions_dict[row_android_version[0]] = value + ", " + row_android_version[1]
# Loop on each jira issue
for bug in bug_id_jira_issue_dict:
    if bug not in bug_id_android_versions_dict:
        continue
    # Get the description from bug_id_jira_id_dict and update the android
    # version with the one stored in bug_id_android_versions_dict
    issue = bug_id_jira_issue_dict.get(bug)
    description = issue.fields.description
    description = description.replace(ANDROID_VERSION_KEY, bug_id_android_versions_dict.get(bug))
    # push the result on jira
    issue.update(description= description)
    print("Updated JIRA issue https://{}.atlassian.net/browse/{}".format(jira_instance, issue.key))

# Add Attachments to issues
print("\nAdding attachments to JIRA issues...\n")
# Loop on attachment table
for row_attachment in rows_attachments:
    if row_attachment[0] not in bug_id_jira_issue_dict:
        continue
    issue = bug_id_jira_issue_dict.get(row_attachment[0])
    filename = row_attachment[1]
    description = row_attachment[2]
    attachment_file = open('./' + filename, 'wb')
    attachment_file.write(row_attachment[3])
    attachment_file.close()
    # Reopen the file in 'rb' as JIRA really want that
    attachment_file = open('./' + filename, 'rb')
    # Add attachment to jira
    jira.add_attachment(issue, attachment_file, filename)
    attachment_file.close()
    os.remove('./' + filename)
    comment = "Add an attached file : [^{}]\n\n{}".format(filename, description)
    # Add a comment in jira issue with a description of the attachment
    jira.add_comment(issue, comment)
    print("Added attachment {} to issue https://{}.atlassian.net/browse/{}" \
          .format(filename, jira_instance, issue.key))

# Add comments to issues
print("\nAdding comments to JIRA issues...\n")
# Create an array to list the issue who already have a description, as
# the first bugzilla comment will be the JIRA description
issues_with_description = []
# Loop on comments table
for row_comments in rows_comments:
    if row_comments[0] not in bug_id_jira_issue_dict:
        continue
    issue = bug_id_jira_issue_dict.get(row_comments[0])
    long_comment = "{0}, by {1[1]}:\n{1[3]}".format(str(row_comments[2]), row_comments)
    if issue.key not in issues_with_description:
        # Get the description from bug_id_jira_id_dict and update the
        # description with the one stored in row_comments
        description = issue.fields.description
        description = description.replace(DESCRIPTION_KEY, long_comment)
        # Push the result on jira
        issue.update(description= description)
        print("Updated JIRA issue description https://{}.atlassian.net/browse/{}" \
              .format(jira_instance, issue.key))
        issues_with_description.append(issue.key)
    else:
        # Add the comment as... comment in the issue
        jira.add_comment(issue, long_comment)
        print("Added comment to issue https://{}.atlassian.net/browse/{}" \
              .format(jira_instance, issue.key))

# Add users from duplicates for each issues
print("\nAdding Users from duplicates to JIRA issues...\n")
# Loop on duplicates users table to fill the jira issues
for row_dup_users in rows_dup_users:
    if row_dup_users[0] not in bug_id_jira_issue_dict:
        continue
    # Get the description from bug_id_jira_id_dict and update the list of
    # users with the one stored in row_dup_users
    issue = bug_id_jira_issue_dict.get(row_dup_users[0])
    description = issue.fields.description
    description = description.replace(DUPLICATES_USERS_KEY, row_dup_users[1])
    # push the result on jira
    issue.update(description= description)
    print("Updated JIRA issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, issue.key))

# Add Attachments from duplicates to issues
print("\nAdding attachments from duplicates to JIRA issues...\n")
# Loop on duplicates attachments table
for row_dup_attachment in rows_dup_attachments:
    if row_dup_attachment[0] not in bug_id_jira_issue_dict:
        continue
    issue = bug_id_jira_issue_dict.get(row_dup_attachment[0])
    filename = row_dup_attachment[1]
    description = row_dup_attachment[2]
    attachment_file = open('./' + filename, 'wb')
    attachment_file.write(row_dup_attachment[3])
    attachment_file.close()
    # Reopen the file in 'rb' as JIRA really want that
    attachment_file = open('./' + filename, 'rb')
    # Add attachment to jira
    jira.add_attachment(issue, attachment_file, filename)
    attachment_file.close()
    os.remove('./' + filename)
    comment = "Add an attached file : [^{}]\n\n{}".format(filename, description)
    # Add a comment in jira issue with a description of the attachment
    jira.add_comment(issue, comment)
    print("Added attachment {} to issue https://{}.atlassian.net/browse/{}" \
          .format(filename, jira_instance, issue.key))

# Add comments from duplicates to issues
print("\nAdding comments from duplicates to JIRA issues...\n")
# Loop on comments from duplicates table
for row_dup_comments in rows_dup_comments:
    if row_dup_comments[0] not in row_dup_comments:
        continue
    issue = bug_id_jira_issue_dict.get(row_dup_comments[0])
    long_comment = "{0}, by {1[1]}:\n{1[3]}".format(str(row_dup_comments[2]), row_dup_comments)
    # Add the comment as... comment in the issue
    jira.add_comment(issue, long_comment)
    print("Added comment to issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, issue.key))

# Clean Description to remove unwanted Description, Android version and Duplicates users keys
print("\nClean the description of all JIRA issues...\n")
for issue in bug_id_jira_issue_dict.values():
    description = issue.fields.description
    description = description.replace(DESCRIPTION_KEY, "") \
                             .replace(ANDROID_VERSION_KEY, "") \
                             .replace(DUPLICATES_USERS_KEY, "")
    # push the result on jira
    issue.update(description= description)
    print("Cleaned JIRA issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, issue.key))

print("\nThat's all folks, keep the vibe and stay true!\nCmoaToto\n")
