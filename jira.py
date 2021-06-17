from flask import Flask
from flask import request
import json
import requests
import events
import logging


def xstr(s):
    return '' if s is None else str(s)


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

    @classmethod
    def create(cls, title, value, short=True):
        field = AttachmentField()
        field.title = xstr(title)
        field.value = xstr(value)
        field.short = short
        return field


class User:
    def __init__(self):
        self.avatar = ''
        self.display_name = ''
        self.email_address = ''
        self.key = ''
        self.name = ''

    @classmethod
    def from_data(cls, data):
        u = User()
        u.avatar = data.get("avatarUrls", {}).get("48x48", "")
        u.display_name = data.get("displayName", "-")
        u.email_address = data.get("emailAddress", "")
        u.key = data['key']
        u.name = data.get("name", "")
        return u

    def mm_link(self):
        return "[" + self.name + "](" + jira_url + \
               "secure/ViewProfile.jspa?name=" + self.key + ")"


class Comment:
    def __init__(self):
        self.id = ''
        self.body = ''
        self.created = ''
        self.updated = ''
        self.author = None
        self.update_author = None

    @classmethod
    def from_data(cls, data):
        c = Comment()
        c.author = User.from_data(data['author']) if data['author'] is not None else None
        c.update_author = User.from_data(data['updateAuthor']) if data['updateAuthor'] is not None else None
        c.id = data['id']
        c.body = data.get("body", "")
        c.created = data.get("created", "")
        c.updated = data.get("updated", "")
        return c

    def mm_link(self, issue_key):
        return "[" + self.body + "](" + jira_url + "browse/" + \
               issue_key + "?focusedCommentId=" + self.id + \
               "&page=com.atlassian.jira.plugin.system.issuetabpanels%3A" + \
               "comment-tabpanel#comment-" + self.id + ")"


class Issue:
    def __init__(self):
        self.assignee = None
        self.creator = None
        self.reporter = None
        self.comments = None
        self.created = ''
        self.updated = ''
        self.description = ''
        self.environment = ''
        self.type = ''
        self.labels = ''
        self.priority = ''
        self.project = None
        self.resolution = ''
        self.status = ''
        self.summary = ''
        self.key = ''

    @classmethod
    def from_data(cls, data):
        i = Issue()
        i.key = data['key']
        fields = data.get("fields", {})
        i.assignee = User.from_data(fields['assignee']) if fields['assignee'] is not None else None
        i.creator = User.from_data(fields['creator']) if fields['creator'] is not None else None
        i.reporter = User.from_data(fields['reporter']) if fields['reporter'] is not None else None
        i.comments = [Comment.from_data(c) for c in fields['comment']['comments']]
        i.created = fields.get("created", "")
        i.updated = fields.get("updated", "")
        i.description = xstr(fields.get("description", "")).strip()
        i.environment = xstr(fields.get("environment", "")).strip()
        i.type = fields.get("issuetype", {}).get("name", "-")
        i.labels = fields.get("labels", "-")
        i.priority = str(fields.get("priority", {}).get("name", ""))
        i.project = Project.from_data(fields['project']) if fields['project'] is not None else None
        i.resolution = str(fields.get("resolution", ""))
        i.status = str(fields.get("status", {}).get("name", ""))
        i.summary = xstr(fields.get("summary", "")).strip()
        return i

    def mm_link(self):
        link = jira_url + "projects/" + self.project.key + "/issues/" + self.key
        return "[%s %s](%s)" % (self.key, self.summary, link)


class Project:
    def __init__(self):
        self.id = ''
        self.key = ''
        self.name = ''
        self.project_lead = None

    @classmethod
    def from_data(cls, data):
        p = Project()
        p.id = data['id']
        p.key = data['key']
        p.name = data['name']
        p.project_lead = User.from_data(data.get("projectLead", {})) if data.get("projectLead", None) is not None else None
        return p

    def mm_link(self):
        return "[" + self.name + "](" + jira_url + "projects/" + \
               self.key + ")"


class Changelog:
    def __init__(self):
        self.items = None

    def description(self):
        output = ""
        if len(self.items) > 1:
            output = "\n"
        for item in self.items:
            output += "Field **" + item.field + "** updated from _" + \
                      item.from_string + "_ to _" + \
                      item.to_string + "_\n"
        return output

    @classmethod
    def from_data(cls, data):
        changelog = Changelog()
        changelog.items = [ChangelogItem.from_data(i) for i in data['items']]
        return changelog


class ChangelogItem:
    def __init__(self):
        self.field = ''
        self.from_string = ''
        self.to_string = ''

    @classmethod
    def from_data(cls, data):
        item = ChangelogItem()
        item.field = data['field']
        item.from_string = data.get("fromString", "") if data.get("fromString", "<empty>") is not None else "<empty>"
        item.to_string = data.get("toString", "") if data.get("toString", "<empty>") is not None else "<empty>"
        return item


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

    logging.info("Using settings url(%s) user(%s) icon(%s) jira_url(%s)"
                 % (mattermost_url, mattermost_user, mattermost_icon, jira_url))


def send_webhook(webhook_url, text, attachment, logger):
    data = {
        'text': text,
        "username": mattermost_user,
        "icon_url": mattermost_icon,
    }

    if attachment is not None:
        data["attachments"] = [attachment.to_dict()]

    logger.debug("sending: %s" % data)
    logger.debug("to url: %s" % webhook_url)

    response = requests.post(
        webhook_url,
        data=json.dumps(data),
        headers={'Content-Type': 'application/json',
                 'charset': 'UTF-8'}
    )

    logger.debug("got response: %s" % response.text)
    return response


def format_fallback_text(project, event, user):
    return "" + \
           "**Project**: " + project.name + "\n" \
           "**Action**: " + event + "\n" \
           "**User**: " + user.display_name


def format_text(project, event, user):
    return "" + \
           "**Project**: " + project.mm_link() + "\n" \
           "**Action**: " + event + "\n" + \
           "**User**: " + user.mm_link()


def get_jira_event_text(jira_event):
    return events.jira_events.get(jira_event, "")


def is_jira_event_supported(jira_event):
    return events.jira_events.get(jira_event, "") != ""


def jira_issue_created_to_message(issue, user) -> Message:
    attachment = Attachment()
    attachment.pretext = "New issue created %s in %s by %s" \
                         % (issue.mm_link(),
                            issue.project.mm_link(),
                            user.mm_link())
    attachment.color = attachment_color

    attachment.fallback = format_fallback_text(issue.project,
                                               "New issue created %s %s" % (issue.key, issue.summary),
                                               user)
    attachment.text = issue.description
    attachment.fields.append(AttachmentField.create("Type", issue.type))
    attachment.fields.append(AttachmentField.create("Priority", issue.priority))
    if issue.creator:
        attachment.fields.append(AttachmentField.create("Creator", issue.creator.display_name))
    if issue.assignee:
        attachment.fields.append(AttachmentField.create("Assignee", issue.assignee.display_name))

    return Message(None, attachment)


def jira_issue_assigned_to_message(issue, user) -> Message:
    attachment = Attachment()
    attachment.pretext = "Assigned %s in %s by %s" \
                         % (issue.mm_link(),
                            issue.project.mm_link(),
                            user.mm_link())
    attachment.color = attachment_color

    attachment.fallback = format_fallback_text(issue.project,
                                               "Issue assigned %s %s" % (issue.key, issue.summary),
                                               user)
    attachment.text = issue.description
    attachment.fields.append(AttachmentField.create("Type", issue.type))
    attachment.fields.append(AttachmentField.create("Priority", issue.priority))
    if issue.creator:
        attachment.fields.append(AttachmentField.create("Creator", issue.creator.display_name))
    if issue.assignee:
        attachment.fields.append(AttachmentField.create("Assignee", issue.assignee.display_name))

    return Message(None, attachment)


def jira_issue_commented_to_message(issue, comment, user) -> Message:
    attachment = Attachment()
    attachment.pretext = "%s %s in %s by %s" \
                         % ("Comment added",
                            issue.mm_link(),
                            issue.project.mm_link(),
                            user.mm_link())
    attachment.color = attachment_color

    attachment.fallback = format_fallback_text(issue.project,
                                               "Issue commented %s %s" % (issue.key, issue.summary),
                                               user)
    attachment.text = comment.body
    attachment.fields.append(AttachmentField.create("Type", issue.type))
    attachment.fields.append(AttachmentField.create("Priority", issue.priority))
    if issue.creator:
        attachment.fields.append(AttachmentField.create("Creator", issue.creator.display_name))
    if issue.assignee:
        attachment.fields.append(AttachmentField.create("Assignee", issue.assignee.display_name))

    return Message(None, attachment)


def jira_issue_comment_deleted_to_message(issue, user) -> Message:
    attachment = Attachment()
    attachment.pretext = "%s %s in %s by %s" \
                         % ("Comment deleted",
                            issue.mm_link(),
                            issue.project.mm_link(),
                            user.mm_link())
    attachment.color = attachment_color

    attachment.fallback = format_fallback_text(issue.project,
                                               "Comment deleted on %s %s" % (issue.key, issue.summary),
                                               user)
    attachment.fields.append(AttachmentField.create("Type", issue.type))
    attachment.fields.append(AttachmentField.create("Priority", issue.priority))
    if issue.creator:
        attachment.fields.append(AttachmentField.create("Creator", issue.creator.display_name))
    if issue.assignee:
        attachment.fields.append(AttachmentField.create("Assignee", issue.assignee.display_name))

    return Message(None, attachment)

def jira_issue_updated_to_message(issue, user, changelog):
    attachment = Attachment()
    attachment.pretext = "%s %s in %s by %s" \
                         % ("Issue updated",
                            issue.mm_link(),
                            issue.project.mm_link(),
                            user.mm_link())
    attachment.color = attachment_color

    attachment.fallback = format_text(issue.project,
                            issue.mm_link() + " " + changelog.description(),
                            user)
    for item in changelog.items:
        attachment.fields.append(AttachmentField.create("Field", item.field, short=False))
        attachment.fields.append(AttachmentField.create("from", item.from_string))
        attachment.fields.append(AttachmentField.create("to", item.to_string))

    return Message(None, attachment)

def jira_issue_event_to_message(data, logger) -> Message:
    jira_event = data["webhookEvent"]
    issue = Issue.from_data(data['issue'])
    event_user = User.from_data(data['user'])

    logger.debug("jira event: %s" % jira_event)

    if jira_event == "jira:issue_created":
        return jira_issue_created_to_message(issue, event_user)

    if jira_event == "jira:issue_updated":
        issue_event_type = data["issue_event_type_name"]

        logger.debug("issue event type: %s" % issue_event_type)

        if issue_event_type == "issue_assigned":
            return jira_issue_assigned_to_message(issue, event_user)

        if issue_event_type == "issue_generic" \
                or issue_event_type == "issue_updated":
            changelog = Changelog.from_data(data['changelog'])
            return jira_issue_updated_to_message(issue, event_user, changelog)

        if issue_event_type == "issue_commented" or issue_event_type == "issue_comment_edited":
            comment = Comment.from_data(data['comment'])
            return jira_issue_commented_to_message(issue, comment, event_user)

        if issue_event_type == "issue_comment_deleted":
            return jira_issue_comment_deleted_to_message(issue, event_user)

    return None


def jira_project_event_to_message(data) -> Message:
    project = Project.from_data(data['project'])
    jira_event = data["webhookEvent"]
    jira_event_text = get_jira_event_text(jira_event)
    return format_text(project,
                       jira_event_text,
                       project.project_lead)


def jira_event_to_message(data, logger) -> Message:
    jira_event = data["webhookEvent"]

    if not is_jira_event_supported(jira_event):
        logger.warning("Received unsupported Jira event: %s" % jira_event)
        return None

    if jira_event.startswith("jira:issue"):
        logger.info("Received Jira issue event for: %s" % data.get("issue_event_type_name", "undefined"))
        return jira_issue_event_to_message(data, logger)

    if jira_event == "project_created":
        logger.info("Received project created event")
        return jira_project_event_to_message(data)

    return None


def handle_channel_hook(webhook_token, data, logger):
    message = jira_event_to_message(data, logger)
    if message is not None:
        webhook_url = "%s/hooks/%s" % (mattermost_url, webhook_token)
        send_webhook(webhook_url, message.text if message.attachment is None else None, message.attachment, logger)
    else:
        logger.info("Received Jira event could not be transformed to Mattermost message.")


def get_json(request, logger):
    request_json = request.get_json()
    if request_json is None or len(request_json) == 0:
        logger.warning("Received a request with empty or non-JSON body")
        return None
    else:
        logger.debug("received request: %s" % json.dumps(request_json))
        return request_json


"""
------------------------------------------------------------------------------------------
Flask application below
"""
read_config()

app = Flask(__name__)
logging.basicConfig(format='%(asctime)-15s %(message)s')


@app.before_first_request
def setup_logging():
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)


@app.route('/hooks/<hook_path>', methods=['POST'])
def channel_webhook(hook_path):
    request_json = get_json(request, app.logger)
    if request_json is not None:
        app.logger.info("Received webhook call for hook '%s'" % (hook_path))
        handle_channel_hook(hook_path, request_json, app.logger)

    return ""


@app.route('/', methods=['GET'])
def index():
    return "<html><body><h1>Mattermost Jira Bridge</h1>See README.md for further details.</body></html>"


if __name__ == '__main__':
    app.run(host=application_host, port=application_port,
            debug=application_debug)
