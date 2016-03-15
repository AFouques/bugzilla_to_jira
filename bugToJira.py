#!/usr/bin/env python3

import getpass
import os
from collections import namedtuple
from jira import JIRA
import mysql.connector

DESCRIPTION_KEY = '[DESCRIPTION_KEY]'
DUPLICATES_USERS_KEY = '[DUPLICATES_USERS_KEY]'
JIRA_LABEL = 'From_Bugzilla'

# Classes!

Bug = namedtuple('Bug', ['bug_id',
                         'severity',
                         'status',
                         'creation',
                         'short_desc',
                         'op_sys',
                         'priority',
                         'product',
                         'platform',
                         'version',
                         'component',
                         'issue_type',
                         'list_users',
                         'zendesk_ticket_id'])

# SQL Requests!

bug_sql_request = """
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

    ORDER BY b.bug_id"""

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

def get_mysql_connection():
    """Get Bugzilla DB info and connect"""
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
    return mysql_conn

def get_jira_connection():
    """Get JIRA info and connect"""
    jira_username = get_value("JIRA username: ", is_mandatory=True)
    jira_password = get_value("JIRA password: ", is_mandatory=True, is_password=True)
    jira_instance = get_value("JIRA instance: https://[yourJiraInstance].atlassian.net: ", is_mandatory=True)
    jira_project = get_value("JIRA project [TEST]: ", default_value = 'TEST')

    print("\nConnecting to your JIRA instance...")
    jira_options = {'server': 'https://{}.atlassian.net'.format(jira_instance)}
    jira = JIRA(jira_options, basic_auth=(jira_username, jira_password))
    print("Connected.\n")
    return jira, jira_instance, jira_project

def create_bug_description(bug, zendesk_instance):
    """Create the description string of a bug from the Bug resource"""
    return """[CREATED]: {}
[Platform]: {}
[Affected users]: {} {}
[Zendesk ticket]: https://{}.zendesk.com/agent/tickets/{}
[Description]:
{}""".format(bug.creation,
             bug.platform,
             bug.list_users, DUPLICATES_USERS_KEY,
             zendesk_instance,
             bug.zendesk_ticket_id,
             DESCRIPTION_KEY)

def is_a_bug(issue):
    """Check the type of the JIRA issue and return if it is a bug or not"""
    return issue.fields.issuetype.name == 'Bug'

# Script!

print("\nWelcome to this awesome script which will migrate your bugzilla " + \
" tickets to your JIRA instance. please give us all your personnal informations.\n")

mysql_conn = get_mysql_connection()
jira, jira_instance, jira_project = get_jira_connection()

# Get Zendesk instance to create cool links
zendesk_instance = get_value("Zendesk instance: https://[yourZendeskInstance].zendesk.com: ",
                             is_mandatory=True)

# Load bugs from bugzilla
print("\nLoading bugs...")
cursor_bugs = mysql_conn.cursor()
cursor_bugs.execute(bug_sql_request)

# We will store a dict with bugzilla {bug id: jira issue} to, then, add
# android versions, comments and attachments
bug_id_jira_issue_dict = {}

# Create JIRA issues from bugs (without comments, attachments and Android versions)
print("Creating JIRA issue for each bug...\n")
for row_bug in cursor_bugs:
    bug = Bug(*row_bug)
    print("Loading bug {} : {}".format(bug.bug_id, bug.short_desc))
    issue_summary = '[BZ{}] {}'.format(bug.bug_id, bug.short_desc)
    issue_description = create_bug_description(bug, zendesk_instance)
    priority = bug.priority.replace("Normal", "Medium").replace("---", "Medium")
    issue_dict = {'project': jira_project,
                  'summary': issue_summary,
                  'description': issue_description,
                  'priority': {'name': priority},
                  'labels': [JIRA_LABEL]}
    issue_type = 'Story'
    if bug.issue_type in ['Ticket', 'Problem']:
        issue_type = 'Bug'
        severity = bug.severity.replace("---", "normal").replace("-", " ")
        status = bug.status.replace("---", "TO_CHECK") \
                                 .replace("-", " ") \
                                 .replace("_", " ") \
                                 .capitalize()
        product = bug.product.replace('Plugins', 'Genymotion Plugin')
        component = bug.component.title() \
                                     .replace('Vm', 'VM') \
                                     .replace('Idea', 'IDEA') \
                                     .replace('Gmtool', 'GMTool')
        issue_dict.update({'versions': [{'name': bug.version}],
                           'customfield_10600': {'value': severity},
                           'customfield_10601': {'value': status},
                           'customfield_10700': {'value': bug.op_sys},
                           'customfield_10701': {'value': product},
                           'customfield_10702': {'value': bug.platform},
                           'customfield_10704': {'value': component}})
    issue_dict['issuetype'] = {'name': issue_type}
    new_issue = jira.create_issue(fields=issue_dict)
    bug_id_jira_issue_dict[bug.bug_id] = new_issue
    print("Created JIRA issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, new_issue.key))

# Load android versions
print("\nLoading android versions...")
cursor_android_version = mysql_conn.cursor()
cursor_android_version.execute("""
    SELECT av.bug_id, av.value
    FROM bug_cf_android_version av""")

# Add Android versions for each issues
print("Adding Android versions to JIRA issues...")
# Create a dict with bug_id | android versions
bug_id_android_versions_dict = {}
# Loop on android versions table to fill the dict
for row_android_version in cursor_android_version:
    value = bug_id_android_versions_dict.get(row_android_version[0])
    if value is None:
        bug_id_android_versions_dict[row_android_version[0]] = [{'value': row_android_version[1]}]
    else:
        value.append({'value': row_android_version[1]})
# Loop on each jira issue
for bug in bug_id_jira_issue_dict:
    if bug not in bug_id_android_versions_dict or not is_a_bug(bug_id_jira_issue_dict.get(bug)) :
        continue
    # Get the issue from bug_id_jira_issue_dict and update the android
    # version with the one stored in bug_id_android_versions_dict
    issue = bug_id_jira_issue_dict.get(bug)
    android_versions = bug_id_android_versions_dict.get(bug)
    # push the result on jira
    issue.update(fields={'customfield_10703': android_versions})
    print("Updated JIRA issue https://{}.atlassian.net/browse/{}".format(jira_instance, issue.key))

# Load attachments
print("\nLoading attachments...")
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

# Add Attachments to issues
print("Adding attachments to JIRA issues...")
# Loop on attachment table
for row_attachment in cursor_attachments:
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

# Load comments
print("\nLoading comments...")
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

# Add comments to issues
print("Adding comments to JIRA issues...")
# Create an array to list the issue who already have a description, as
# the first bugzilla comment will be the JIRA description
issues_with_description = []
# Loop on comments table
for row_comments in cursor_comments:
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

# Load listusers from duplicates
print("\nLoading users from duplicates...")
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

# Add users from duplicates for each issues
print("Adding Users from duplicates to JIRA issues...")
# Loop on duplicates users table to fill the jira issues
for row_dup_users in cursor_dup_users:
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

# Load attachments from duplicates
print("\nLoading attachments from duplicates...")
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

# Add Attachments from duplicates to issues
print("Adding attachments from duplicates to JIRA issues...")
# Loop on duplicates attachments table
for row_dup_attachment in cursor_dup_attachments:
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

# Load comments from duplicates
print("\nLoading comments from duplicates...")
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

# Add comments from duplicates to issues
print("Adding comments from duplicates to JIRA issues...")
# Loop on comments from duplicates table
for row_dup_comments in cursor_dup_comments:
    if row_dup_comments[0] not in bug_id_jira_issue_dict:
        continue
    issue = bug_id_jira_issue_dict.get(row_dup_comments[0])
    long_comment = "{0}, by {1[1]}:\n{1[3]}".format(str(row_dup_comments[2]), row_dup_comments)
    # Add the comment as... comment in the issue
    jira.add_comment(issue, long_comment)
    print("Added comment to issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, issue.key))

print("\nDisconnecting from your MySQL database...")
mysql_conn.close()
print("Disconnected.\n")

# Clean Description to remove unwanted Description, Android version and Duplicates users keys
print("\nClean the description of all JIRA issues...")
for issue in bug_id_jira_issue_dict.values():
    description = issue.fields.description
    description = description.replace(DESCRIPTION_KEY, "") \
                             .replace(DUPLICATES_USERS_KEY, "")
    # push the result on jira
    issue.update(description= description)
    print("Cleaned JIRA issue https://{}.atlassian.net/browse/{}" \
          .format(jira_instance, issue.key))

print("\nThat's all folks, keep the vibe and stay true!\nCmoaToto\n")
