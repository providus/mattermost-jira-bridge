# JIRA Webhook Bridge for Mattermost

This repository contains a Python Flask application that accepts webhooks from [JIRA
Server](https://www.atlassian.com/software/jira) and forwards them to the specified
channel, or channels, in a [Mattermost](https://mattermost.com) server via an incoming webhook.

Currently the application supports the following JIRA event types:

* Project Created
* Issue Created
* Issue Edited
* Issue Commented
* Issue Comment - Edited
* Issue Comment - Deleted
* Issue Assigned  
* Issue Updated (any changelog)

# Installation, Configuration, and Execution

The following section describes how to install, configure and run the Flask application.

## Installation

The easiest way to install this application is to:

1. Log into the machine that will host the Python Flask application;
2. Clone this repository;
3. Create a webhook in Mattermost to accept posts from JIRA (**Note**: You will need the URL for
this webhook when configuring the application below.)

## Configuration

Once the application has been cloned it needs to be configured for your environment and
how your organization uses JIRA. The following instructions cover configuration:

1. Change directories to the application's root: `cd mattermost-jira-bridge`;
2. Make a copy of `config.sample` as `config.json`: `cp config.sample config.json`
3. Open the `config.json` file using your favorite editor (e.g. `sudo nano config.json`) and make the
edits to each section as described below:

**Application**

The `application` section setups up the runtime environment of the Flask application. For most uses
you can leave this as-is or simply update the port to the desired port for your environment.

```
	"application" : {
		"host" : "0.0.0.0",
		"port" : 5007,
		"debug" : false
	}
```

If you do not want the Flask application to be accessible from other machines you can 
update the host address to `127.0.0.1`. You can also enable Flask's debug mode by 
changing `debug` to `true`.

**Features**

The `features` section allows you to configure how messages map to Mattermost channels based 
on JIRA project and whether or not the issue is labeled as a bug. The channel mapping has
the following options:

* All messages are sent to the default channel configured in the Mattermost webhook;

**Colors**

The `colors` section has one setting, `attachment`,  which sets the highlight color
of the message if sent as a 
[Message Attachment](https://docs.mattermost.com/developer/message-attachments.html).
**Note**: The default color that the application ships with is green.

```
	"colors" : {
		"attachment" : "#28c12b"
	}
```

**Mattermost**

The `mattermost` section is used to configure the Mattermost web hook that the application
will post messages to. You can optionally add a user name and icon to override the 
default configured in Mattermost.

```
	"mattermost" : {
		"webhook" : "https://mattermost.url/hooks/webhookid",
		"post_user_name" : "JIRA",
		"post_user_icon" : ""
	}
```

**JIRA**

The `jira` section has one setting for the base URL of your JIRA server. This setting is used
to generate links in messages the application posts to Mattermost.

```
	"jira" : {
		"url" : "http://jira.url:8080/"
	}
```

### JIRA Webhook

The following steps describe how to setup the JIRA webhook:

1. Select `System` from the `Administration` menu (**Note**: You must have administrative rights.)
2. Click on `WebHooks` in the `Advanced` section.
3. Click on the `Create a WebHook` button at the top right of the page.
4. Fill in the `New WebHook Listener` form:
    * Enter a name for your webhook;
    * Click on `Enabled` for `Status` to ensure that the webhook fires;
    * Webhook URL:
		* If project to channel mapping is used, enter the address of your running bridge application and append `/${project.key}` to the end 
      (example:` https://bridge.url/jira/${project.key}`) so that JIRA will pass
      the project key via the URL to bridge application.
		* If the channel is configured in the webhook, enter the address of the bridge application and append `/channel/<channel name>`
		(example: `https://bridge.url/jira/channel/town-square`)
    * Select the events that you want to send from JIRA to Mattermost (**Note**: only the
      events listed in the introduction above are currently supported however unsupported
      events will not cause application failures.)
5. Click on the `Create` button to finish creating the webhook.


## Execution

Once the application is configured that are a number of ways to run it. The simplest for 
testing purposes is:

`sudo python jira.py`

For longer term execution I use the following command that runs the application headlessly 
and captures output into a log file for troubleshooting:

```
sudo python jira.py >> jira.log 2>&1 &
```


# Make this Project Better (Questions, Feedback, Pull Requests Etc.)

**Help!** If you like this project and want to make it even more awesome please contribute your ideas,
code, etc.

If you have any questions, feedback, suggestions, etc. please submit them via issues here: https://github.com/cvitter/mattermost-jira-bridge/issues

If you find errors please feel to submit pull requests. Any help in improving this resource is appreciated!

# License
The content in this repository is Open Source material released under the MIT License. Please see the [LICENSE](LICENSE) file for full license details.

# Disclaimer

The code in this repository is not sponsored or supported by Mattermost, Inc.

# Authors
* Author: [Craig Vitter](https://github.com/cvitter)

# Contributors 

Please submit Issues and/or Pull Requests.
