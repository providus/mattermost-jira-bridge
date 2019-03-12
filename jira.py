from flask import Flask
from flask import request
import json
import requests
import events
import logging


def read_config():
    """
    Reads config.json to get configuration settings
    """
    with open('config.json') as config_file:
        d = json.loads(config_file.read())

    global application_host, application_port, application_debug
    application_host = d["application"]["host"]
    application_port = d["application"]["port"]
    application_debug = d["application"]["debug"]

    global use_project_to_channel_map, use_project_bugs_to_channel_map
    global use_project_to_channel_pattern, project_to_channel_pattern
    global use_bug_specific_channel, bug_channel_postfix
    global use_attachments
    use_project_to_channel_map = d["features"]["use_project_to_channel_map"]
    use_project_bugs_to_channel_map = d["features"]["use_project_bugs_to_channel_map"]
    use_project_to_channel_pattern = d["features"]["use_project_to_channel_pattern"]
    project_to_channel_pattern = d["features"]["project_to_channel_pattern"]
    use_bug_specific_channel = d["features"]["use_bug_specific_channel"]
    bug_channel_postfix = d["features"]["bug_channel_postfix"]
    use_attachments = d["features"]["use_attachments"]

    global attachment_color
    attachment_color = d["colors"]["attachment"]

    global webhook_url, mattermost_user, mattermost_icon
    webhook_url = d["mattermost"]["webhook"]
    mattermost_user = d["mattermost"]["post_user_name"]
    mattermost_icon = d["mattermost"]["post_user_icon"]

    global jira_url
    jira_url = d["jira"]["url"]


def get_project_from_json(project_key):
    project_key = project_key.lower()
    with open('projects.json') as project_file:
        d = json.loads(project_file.read())
    channel_by_project = {k.lower(): v for k, v in d["projects"].items()}
    return channel_by_project.get(project_key, "")


def get_channel(project_key, issue_type):
    """
    Returns the Mattermost channel to post into based on
    settings in config.json or returns "" if no
    Mattermost channel has been configured
    """
    channel = ""
    if use_project_to_channel_map:
        if use_project_bugs_to_channel_map and issue_type.lower() == "bug":
            channel = get_project_from_json(project_key + "-bug")
        if len(channel) == 0:
            channel = get_project_from_json(project_key)

    if use_project_to_channel_pattern and len(channel) == 0:
        channel = project_to_channel_pattern + project_key
        if use_bug_specific_channel and issue_type.lower() == "bug":
            channel += bug_channel_postfix

    return channel


def send_webhook(channel, text, logger):
    data = {
        "channel": channel,
        "username": mattermost_user,
        "icon_url": mattermost_icon
    }

    if use_attachments:
        data["attachments"] = [{
            "color": attachment_color,
            "text": text
        }]
    else:
        data["text"] = text

    logger.debug("sending %s" % data)

    response = requests.post(
        webhook_url,
        data=json.dumps(data),
        headers={'Content-Type': 'application/json'}
    )
    return response

def send_mapped_project_webhook(project_key, issue_type, text, logger):
    """
    Sends the formatted message to the configured
    Mattermost webhook URL
    """
    if len(project_key) == 0:
        return

    channel = get_channel(project_key, issue_type)
    send_webhook(channel, text, logger)


def user_profile_link(user_id, user_name):
    return "[" + user_name + "](" + jira_url + \
        "secure/ViewProfile.jspa?name=" + user_id + ")"


def project_link(project_name, project_key):
    return "[" + project_name + "](" + jira_url + "projects/" + \
        project_key + ")"


def issue_link(project_key, issue_id):
    return "[" + issue_id + "](" + jira_url + "projects/" + \
        project_key + "/issues/" + issue_id + ")"


def comment_link(comment, issue_id, comment_id):
    return "[" + comment + "](" + jira_url + "browse/" + \
        issue_id + "?focusedCommentId=" + comment_id + \
        "&page=com.atlassian.jira.plugin.system.issuetabpanels%3A" + \
        "comment-tabpanel#comment-" + comment_id + ")"


def format_new_issue(event, project_key, issue_key, summary, description,
                     priority):
    return "" + \
        event + " " + issue_link(project_key, issue_key) + "\n" \
        "**Summary**: " + summary + " (_" + priority + "_)\n" \
        "**Description**: " + description.encode('ascii','ignore').strip()


def format_changelog(changelog_items):
    """
    The changelog can record 1+ changes to an issue
    """
    output = ""
    if len(changelog_items) > 1:
        output = "\n"
    for item in changelog_items:
        output += "Field **" + item["field"] + "** updated from _" + \
                  item["fromString"].encode('ascii','ignore').strip() + "_ to _" + \
                  item["toString"].encode('ascii','ignore').strip() + "_\n"
    return output


def format_message(project_key, project_name, event, user_id, user_name):
    message = "" + \
        "**Project**: " + project_link(project_key, project_key) + "\n" \
        "**Action**: " + event + "\n" \
        "**User**: " + user_profile_link(user_id, user_name)
    return message

def get_jira_event_text(data):
    jira_event = data["webhookEvent"]
    return events.jira_events.get(jira_event, "")

def jira_issue_event_to_message(data):
    jira_event = data["webhookEvent"]
    issue_type = data["issue"]["fields"]["issuetype"]["name"]
    project_key = data["issue"]["fields"]["project"]["key"]

    if jira_event == "jira:issue_created":
        return format_message(project_key,
                                 data["issue"]["fields"]["project"]["name"],
                                 format_new_issue("New **" + issue_type + "** created for:",
                                                  project_key,
                                                  data["issue"]["key"],
                                                  data["issue"]["fields"]["summary"].encode('ascii','ignore').strip(),
                                                  data["issue"]["fields"]["description"].encode('ascii','ignore').strip(),
                                                  data["issue"]["fields"]["priority"]["name"]),
                                 data["user"]["key"],
                                 data["user"]["displayName"])

    if jira_event == "jira:issue_updated":
        issue_event_type = data["issue_event_type_name"]
        if issue_event_type == "issue_generic" or issue_event_type == "issue_updated":
            return format_message(project_key,
                                     data["issue"]["fields"]["project"]["name"],
                                     issue_link(project_key, data["issue"]["key"]) + " " + \
                                     format_changelog(data["changelog"]["items"]),
                                     data["user"]["key"],
                                     data["user"]["displayName"])

        formatted_event_type = events.issue_events.get(issue_event_type, "")
        if issue_event_type == "issue_commented" or issue_event_type == "issue_comment_edited":
            return format_message(project_key,
                                     data["issue"]["fields"]["project"]["name"],
                                     issue_link(project_key, data["issue"]["key"]) + " " + \
                                     formatted_event_type + "\n" + \
                                     "**Comment**: " + \
                                     comment_link(data["comment"]["body"],
                                                  data["issue"]["key"],
                                                  data["comment"]["id"]),
                                     data["user"]["key"],
                                     data["user"]["displayName"])

        if issue_event_type == "issue_comment_deleted":
            return format_message(project_key,
                                     data["issue"]["fields"]["project"]["name"],
                                     issue_link(project_key, data["issue"]["key"]) + " " + \
                                     formatted_event_type,
                                     data["user"]["key"],
                                     data["user"]["displayName"])
    return None

def jira_project_event_to_message(data):
    project_key = data["project"]["key"]
    jira_event_text = get_jira_event_text(data)
    return format_message(project_key, data["project"]["name"],
                             jira_event_text,
                             data["project"]["projectLead"]["key"],
                             data["project"]["projectLead"]["displayName"])

def jira_event_to_message(data):
    jira_event = data["webhookEvent"]
    jira_event_text = get_jira_event_text(data)

    if len(jira_event_text) == 0:
        """
        Not a supported JIRA event, return None
        and quietly go away
        """
        return None

    if jira_event.startswith("jira:issue"):
        return jira_issue_event_to_message(data)

    if jira_event == "project_created":
        return jira_project_event_to_message(data)

    return None

def handle_mapped_project_hook(project_key, data, logger):
    message = jira_event_to_message(data)
    if message is not None:
        issue_type = data["issue"]["fields"]["issuetype"]["name"]
        send_mapped_project_webhook(project_key, issue_type, message, logger)
    else:
        logger.info("Received project webhook did not match any known events.")

def handle_channel_hook(channel_name, data, logger):
    message = jira_event_to_message(data)
    if message is not None:
        send_webhook(channel_name, message, logger)
    else:
        logger.info("Received channel webhook did not match any known events.")

def get_json(request, logger):
    request_json = request.get_json()
    if request_json is None or len(request_json) == 0:
        app.logger.warning("Received a request with empty or non-JSON body")
        return None
    else:
        app.logger.debug(json.dumps(request_json))
        return request_json

"""
------------------------------------------------------------------------------------------
Flask application below
"""
read_config()

app = Flask(__name__)

@app.before_first_request
def setup_logging():
    if not app.debug:
        app.logger.setLevel(logging.WARN)

@app.route('/jira/<project_key>', methods=['POST'])
def project_webhook(project_key):
    request_json = get_json(request, app.logger)
    if request_json is not None:
        app.logger.info("Received webhook call for project '%s'" % (project_key))
        handle_mapped_project_hook(project_key, request_json, app.logger)

    return ""

@app.route('/jira/channel/<channel_name>', methods=['POST'])
def channel_webhook(channel_name):
    request_json = get_json(request, app.logger)
    if request_json is not None:
        app.logger.info("Received webhook call for channel '%s'" % (channel_name))
        app.logger.debug(request_json)
        handle_channel_hook(channel_name, request_json, app.logger)

    return ""

if __name__ == '__main__':
    app.run(host=application_host, port=application_port,
            debug=application_debug)
