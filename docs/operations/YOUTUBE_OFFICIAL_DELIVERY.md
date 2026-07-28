# Official YouTube delivery

Content Automation supports one account-gated live delivery adapter: `youtube-official`.

The adapter uses the official YouTube Data API, Google OAuth for the selected channel account, resumable video upload, delivery retries and reconciliation through the existing P97 queue. It does not use browser automation, copied cookies, a service account, or private endpoints.

## Safety defaults

- target environment is `staging` during first activation;
- the first target supports `private` uploads only;
- subscriber notifications are disabled;
- AI/synthetic-media disclosure is enabled;
- no automatic fallback transport exists;
- only an approved immutable release can be queued;
- the release output checksum and size must match canonical shared-storage evidence;
- public or unlisted delivery must be enabled explicitly during account setup;
- scheduled publication requires a private upload plus explicit public authorization;
- OAuth refresh tokens remain in `.runtime/youtube-oauth.json`, outside Git and PostgreSQL.

## Google Cloud preparation

Create an OAuth client for a desktop application in the approved Google Cloud project and enable the YouTube Data API. Download the OAuth client JSON to the workstation. Do not commit it.

Google OAuth authorization must be performed by a person who controls the intended YouTube channel.

## Account setup

After P105/P106 are deployed and Creator Studio is healthy, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_youtube_official.ps1 `
  -GoogleOAuthClientJson "C:\secure\youtube-client.json" `
  -ChannelReference "channel:<channel-id-or-name>"
```

This command:

1. opens the official Google consent page;
2. requests only YouTube upload and read-only status scopes;
3. stores the resulting refresh token outside Git;
4. restricts the credential file to the current Windows user;
5. restarts the authenticated ngrok runtime;
6. creates and activates a private-only YouTube delivery target;
7. records readiness without uploading a video.

To permit an unlisted test as well:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_youtube_official.ps1 `
  -GoogleOAuthClientJson "C:\secure\youtube-client.json" `
  -ChannelReference "channel:<channel-id-or-name>" `
  -AllowUnlisted
```

Do not pass `-AllowPublic` until the private test, reconciliation, channel identity and human release decision have all passed.

## First private delivery

1. Complete a content item through script, narration, visual, QA and final release approval.
2. Open **Release & delivery** as Admin or Reviewer.
3. Select the active official YouTube target.
4. Choose `private` privacy.
5. Enter title, caption, hashtags and the required disclosure.
6. Create the delivery request.
7. Claim and execute the request through the existing delivery controls.
8. Confirm the platform reference contains the expected YouTube video ID.
9. Reconcile the platform status.
10. Open YouTube Studio manually and verify the uploaded video belongs to the expected channel, remains private and matches the approved release.
11. Record the human decision before enabling unlisted or public delivery.

## Public activation

Public delivery is not enabled by changing database rows manually. Re-run account setup with `-AllowPublic` only after the private proof is accepted. Keep `-NotifySubscribers` off for the first public proof unless a human explicitly approves subscriber notification.

A public post does not close P100 by itself. The external result must still be recorded against the exact accepted content item with its release, platform reference, review and sign-off evidence.

## Revocation

To revoke access:

1. stop the Content Automation runtime;
2. revoke the application grant in the Google account;
3. remove `.runtime/youtube-oauth.json`;
4. remove `YOUTUBE_CREDENTIAL_FILE` from `.env.local`;
5. mark the YouTube target unavailable or retire it in Creator Studio;
6. restart the runtime and confirm no official YouTube target is executable.
