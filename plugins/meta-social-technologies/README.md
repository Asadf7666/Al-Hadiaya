# Meta Tools for Al Hidaya

Version 0.1.0. A plugin for Codex and compatible Agent Plugins hosts that connects to Meta's official Social Technologies MCP server using OAuth. Published by Al Hidaya Traders; not affiliated with or endorsed by Meta.

## Install with Codex CLI

Install a current Codex CLI with plugin support, then run:

```sh
codex plugin marketplace add Asadf7666/Al-Hadiaya --ref main
codex plugin add meta-social-technologies@al-hidaya-plugins
```

Start a new Codex session. Connect/authenticate the bundled `meta_social_technologies` server when your client prompts you, signing in directly to Meta. Select the intended developer app and begin with Read access. Manage access is needed only for webhook changes. Do not paste your password or tokens into chat.

If using the downloaded ZIP, extract it first and use its marketplace root instead of the GitHub command:

```sh
codex plugin marketplace add /absolute/path/to/AlHidaya-Meta-Plugin-0.1.0
codex plugin add meta-social-technologies@al-hidaya-plugins
```

Try: “Use meta-whatsapp-setup to check my Meta app and tell me what remains for WhatsApp Cloud API setup.”

## Connect from ChatGPT

A local ZIP is not an automatic ChatGPT web plugin installation. If your account supports custom MCP plugins, open https://chatgpt.com/plugins, select the plus button and **Add custom MCP server**. Enter:

- Name: **Meta Tools for Al Hidaya**
- Server URL: **https://mcp.facebook.com/devtools**
- Authentication: **OAuth**

Complete Meta's login and app authorization, then select **Create as a plugin** when offered. Start a new chat after connecting. Availability and button labels depend on your account/client. A registered ChatGPT connection ID is required to bind this connection to a workspace-distributed bundle; this package intentionally contains no invented connection ID.

## What it does

Inspect authorized developer apps, review/compliance status, API usage and changelogs; inspect and, when authorized, manage webhook subscriptions and test events. Includes a guided workflow for the shop's WhatsApp integration.

It does not create Meta apps, verify phone numbers or send WhatsApp messages. Messaging requires separate WhatsApp Cloud API configuration in the shop application. A subscription in the WhatsApp Business mobile app does not provide that API token. Connecting this plugin does not change the shop's offline/online sync.

Meta's service is in beta and may limit clients or accounts. A successful package installation does not prove OAuth or API access. This plugin has no local service, executable hooks or embedded credentials. Requests go directly to Meta; Meta's service terms and privacy policy apply. Never commit app tokens or OAuth credentials to the repository.

## Update / remove

```sh
codex plugin marketplace upgrade al-hidaya-plugins
codex plugin remove meta-social-technologies@al-hidaya-plugins
```

Restart your session after updating. Disconnect/revoke the Meta authorization separately in the client's connection settings or Meta's authorized integrations if required.

## Validation

The manifests were checked against the Agent Plugins 1.0.0 JSON schemas. Codex CLI successfully discovered the plugin in the marketplace with version 0.1.0 and OAuth-on-install policy. No Meta login, webhook changes or messages were performed during validation; live authorization remains to be completed by the user.

References: https://developers.openai.com/plugins/build/plugins and the user-supplied Meta Social Technologies MCP documentation (endpoint https://mcp.facebook.com/devtools).
