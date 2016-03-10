# bugzilla_to_jira
Python script to migrate your Bugzilla ticket to Jira

### Installation

Clone the repo, or download the raw bugToJira.py

Install JIRA python library
```$ sudo pip install jira```

Install MySQL python library:

- For Fedora:
```
$ sudo yum install mysql-connector-python
```
- For Ubuntu:
```
$ sudo apt-get install python-mysqldb
```

### Usage

Run: ```$ ./bugToJira.py```

No argument needed, everything will be prompt

### Real usage for your needs

This script has been created for our company instances of bugzilla and JIRA so some part must be changed when you use it:
- We use our zendesk instance name to keep our zendesk links in our jira issues
- The tables requested might change if you created personnal bugzilla fields.
- The elements of the description might change for the same reason
- If you want to use custom fields in jira to store some values, you'll have to set them up like it is in the script
```issue_dict.update({'customfield_10600': {'value': issue_severity}, 'customfield_10601': {'value': issue_status}})```
- The ```Android Version``` we use in our script is a kind of a trick to keep a n to n table in a list, in the description.

### All ```bugToJira.py``` comments in a row

```
# Functions!

# Get a value from the user

# Script!

# Get Bugzilla DB info and connect
# Get JIRA info and connect
# Get Zendesk instance to create cool links

# Load bugs from bugzilla
# Load android versions
# Load attachments
# Load comments
# Load listusers from duplicates
# Load attachments from duplicates
# Load comments from duplicates
# We will store a dict with bugzilla {bug id: jira issue} to, then, add android versions, comments and attachments

# Create JIRA issues from bugs (without comments, attachments and Android versions)

# Add Android versions for each issues
# Create a dict with bug_id | android versions
# Loop on android versions table to fill the dict
# Loop on each jira issue
    # Get the description from bug_id_jira_id_dict and update the android version with the one stored in bug_id_android_versions_dict
    # push the result on jira

# Add attachments to issues
# Loop on attachment table
    # Reopen the file in 'rb' as JIRA really want that
    # Add attachment to jira
    # Add a comment in jira issue with a description of the attachment

# Add comments to issues
# Create an array to list the issue who already have a description, as the first bugzilla comment will be the JIRA description
# Loop on comments table
    # If first comment
        # Get the description from bug_id_jira_id_dict and update the description with the one stored in row_comments
        # Push the result on jira
    # Else
        # Add the comment as... comment in the issue

# Add users from duplicates for each issues
    # Get the description from bug_id_jira_id_dict and update the list of users with the one stored in row_dup_users
    # push the result on jira

# Add Attachments from duplicates to issues
# Loop on duplicates attachments table
    # Reopen the file in 'rb' as JIRA really want that
    # Add attachment to jira
    # Add a comment in jira issue with a description of the attachment

# Add comments from duplicates to issues
# Loop on comments from duplicates table
    # Add the comment as... comment in the issue

# Clean Description to remove unwanted Description, Android version and Duplicates users keys
    # push the result on jira
```
