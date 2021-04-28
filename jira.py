from flask import Flask
from flask import request
import json
import requests
import events
import logging


class Message:
    def __init__(self, text, attachment):
        self.text = text
        self.attachment = attachment


class Attachment:
    def __init__(self):
        self.author_name = ''
        self.author_icon = ''
        self.author_link = ''
        self.fallback = ''
        self.color = ''
        self.pretext = ''
        self.text = ''
        self.title = ''
        self.fields = []

    def to_dict(self):
        d = self.__dict__
        d['fields'] = [f.__dict__ for f in self.fields]
        return d


class AttachmentField:
    def __init__(self):
        self.short = True
        self.title = ''
        self.value = ''


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

    global attachment_color
    attachment_color = d["colors"]["attachment"]

    global mattermost_url, mattermost_user, mattermost_icon
    mattermost_url = d["mattermost"]["webhook"]
    mattermost_user = d["mattermost"]["post_user_name"]
    mattermost_icon = d["mattermost"]["post_user_icon"]

    global jira_url
    jira_url = d["jira"]["url"]


def send_webhook(webhook_url, text, attachment, logger):
    data = {
        'text': text,
        "username": mattermost_user,
        "icon_url": mattermost_icon,
    }

    if attachment is not None:
        data["attachments"] = [attachment.to_dict()]

    logger.debug("sending %s" % data)

    response = requests.post(
        webhook_url,
        data=json.dumps(data),
        headers={'Content-Type': 'application/json'}
    )
    return response


def user_profile_link(user_id, user_name):
    return "[" + user_name + "](" + jira_url + \
           "secure/ViewProfile.jspa?name=" + user_id + ")"


def project_link(project_name, project_key):
    return "[" + project_name + "](" + jira_url + "projects/" + \
           project_key + ")"


def issue_link(project_key, issue_key, summary):
    link = jira_url + "projects/" + project_key + "/issues/" + issue_key
    return "[%s %s](%s)" % (issue_key, summary, link)


def comment_link(comment, issue_id, comment_id):
    return "[" + comment + "](" + jira_url + "browse/" + \
           issue_id + "?focusedCommentId=" + comment_id + \
           "&page=com.atlassian.jira.plugin.system.issuetabpanels%3A" + \
           "comment-tabpanel#comment-" + comment_id + ")"


def format_new_issue_text(event, project_key, issue_key, summary, description, priority):
    return "" + \
           event + " " + issue_link(project_key, issue_key, summary) + "\n" \
        "**Summary**: " + summary + " (_" + priority + "_)\n" \
        "**Description**: " + description

def format_changelog(changelog_items):
    """
    The changelog can record 1+ changes to an issue
    """
    output = ""
    if len(changelog_items) > 1:
        output = "\n"
    for item in changelog_items:
        fromString = str(item.get("fromString", "-").encode('ascii', 'ignore').strip())
        toString = str(item.get("toString", "-").encode('ascii', 'ignore').strip())
        output += "Field **" + item["field"] + "** updated from _" + \
                  fromString + "_ to _" + \
                  toString + "_\n"
    return output


def format_text(project_key, project_name, event, user_id, user_name):
    return "" + \
            "**Project**: " + project_link(project_name, project_key) + "\n" \
            "**Action**: " + event + "\n" \
            "**User**: " + user_profile_link(user_id, user_name)

def get_jira_event_text(data):
    jira_event = data["webhookEvent"]
    return events.jira_events.get(jira_event, "")


def jira_issue_event_to_message(data) -> Message:
    jira_event = data["webhookEvent"]
    issue_type = data["issue"]["fields"]["issuetype"]["name"]
    project_key = data["issue"]["fields"]["project"]["key"]
    project_name = data["issue"]["fields"]["project"]["name"]
    user_key = data["user"]["key"]
    user_display_name = data["user"]["displayName"]

    if jira_event == "jira:issue_created":
        fields = data["issue"].get("fields", {})
        summary = str(fields.get("summary", "-").encode('ascii', 'ignore').strip())
        description = str(fields.get("description", "-").encode('ascii', 'ignore').strip())
        priority = fields.get("priority", {}).get("name", "-")
        issue_key = data["issue"]["key"]
        text = format_text(project_key,
                           fields.get("project", {}).get("name", "-"),
                           format_new_issue_text("New **" + issue_type + "** created for:",
                                                 project_key,
                                                 issue_key,
                                                 summary,
                                                 description,
                                                 priority),
                           user_key,
                           user_display_name)

        attachment = Attachment()
        attachment.pretext = "New issue created %s in %s by %s" \
                             % (issue_link(project_key, issue_key, summary),
                                project_link(project_name, project_key),
                                user_profile_link(user_key, user_display_name))
        attachment.color = attachment_color

        description_field = AttachmentField()
        description_field.short = False
        description_field.title = "Description"
        description_field.value = description
        attachment.fields.append(description_field)

        type_field = AttachmentField()
        type_field.title = "Type"
        type_field.value = issue_type
        attachment.fields.append(type_field)

        assignee_field = AttachmentField()
        assignee_field.title = "Assignee"
        assignee_field.value = user_key
        attachment.fields.append(assignee_field)

        creator_field = AttachmentField()
        creator_field.title = "Creator"
        creator_field.value = user_key
        attachment.fields.append(creator_field)

        priority_field = AttachmentField()
        priority_field.title = "Priority"
        priority_field.value = priority
        attachment.fields.append(priority_field)

        return Message(text, attachment)

    if jira_event == "jira:issue_updated":
        issue_event_type = data["issue_event_type_name"]
        if issue_event_type == "issue_generic" or issue_event_type == "issue_updated":
            text = format_text(project_key,
                               data["issue"]["fields"]["project"]["name"],
                               issue_link(project_key, data["issue"]["key"], "") + " " + \
                               format_changelog(data["changelog"]["items"]),
                               data["user"]["key"],
                               data["user"]["displayName"])

        return Message(text, None)

        formatted_event_type = events.issue_events.get(issue_event_type, "")
        if issue_event_type == "issue_commented" or issue_event_type == "issue_comment_edited":
            text = format_message(project_key,
                                  data["issue"]["fields"]["project"]["name"],
                                  issue_link(project_key, data["issue"]["key"], "") + " " + \
                                  formatted_event_type + "\n" + \
                                  "**Comment**: " + \
                                  comment_link(data["comment"]["body"],
                                               data["issue"]["key"],
                                               data["comment"]["id"]),
                                  data["user"]["key"],
                                  data["user"]["displayName"])
            return Message(text, None)

        if issue_event_type == "issue_comment_deleted":
            text = format_message(project_key,
                                  data["issue"]["fields"]["project"]["name"],
                                  issue_link(project_key, data["issue"]["key"], "") + " " + \
                                  formatted_event_type,
                                  data["user"]["key"],
                                  data["user"]["displayName"])
            return Message(text, None)

    return None


def jira_project_event_to_message(data) -> Message:
    project_key = data["project"]["key"]
    jira_event_text = get_jira_event_text(data)
    return format_text(project_key, data["project"]["name"],
                       jira_event_text,
                       data["project"]["projectLead"]["key"],
                       data["project"]["projectLead"]["displayName"])


def jira_event_to_message(data) -> Message:
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


def handle_channel_hook(webhook_token, data, logger):
    message = jira_event_to_message(data)
    if message is not None:
        webhook_url = "%s/hook/%s" % (mattermost_url, webhook_token)
        send_webhook(webhook_url, message.text, message.attachment, logger)
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


@app.route('/hooks/<hook_path>', methods=['POST'])
def channel_webhook(hook_path):
    request_json = get_json(request, app.logger)
    if request_json is not None:
        app.logger.info("Received webhook call for hook_path '%s'" % (hook_path))
        app.logger.debug(request_json)
        handle_channel_hook(hook_path, request_json, app.logger)

    return ""


@app.route('/', methods=['GET'])
def index():
    return "<html><body><h1>Mattermost Jira Bridge</h1>See README.md for further details.</body></html>"


if __name__ == '__main__':
    app.run(host=application_host, port=application_port,
            debug=application_debug)
