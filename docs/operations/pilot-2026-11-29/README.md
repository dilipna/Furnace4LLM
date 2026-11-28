# Sunday pilot packet — November 29, 2026

Owner-approved deadline: **Friday, December 4, 2026, end of day, America/New_York**.
Scope: local MVP and private demonstration. The product remains a researcher
infrastructure platform with the free kit and Studio. Documents is an example
application; both journeys require acceptance. The theme stays.
The proposed $20/month service is **Coming later**; no public service, billing,
accounts or internet-facing hosting is included. The hosted-service proposal remains
in [hosted-service-design.md](../../release/hosted-service-design.md).

## Send these to the tester

- [Clean-account install checklist](clean-account-install.md).
- [Participant sheet](participant-sheet.md).
- [Synthetic document](sample-document.txt). It contains no personal/customer data.

Keep [facilitator notes](facilitator-notes.md) separate until tasks are finished.
All actual observations are blank. Estimates exclude account creation, Docker setup
and downloads. Browser automation does not establish human comprehension.

## Which installer?

Today's available preview is **9598d6d**, not the final release candidate:

`Furnace-0.1.0-9598d6d83beb-windows-x64.exe`

SHA-256: `8fdb61c18526a811952edfe3f8aefb90735df22f6a69d2251aa4a7600fc9a02d`

It has installed Studio Qwen/Granite acceptance, but **does not have installed
private-document acceptance**. Its home currently opens researcher Studio; the
document interface is reached through **Example application: documents**. Record
that discoverability honestly. Do not describe this preview as accepted through
both installed journeys.

On Dilip's machine: http://127.0.0.1:4011 while the preview server runs. A different
computer cannot use Dilip's localhost URL. Dilip must privately provide the exact
installer and matching checksum to that tester. Nothing is publicly published.

If a newer build is supplied, record its own full hash and source; this packet's
9598d6d hash cannot validate it. Never copy observations between builds.

## Before the December 4 handoff

1. Today: provide this packet and confirm the private transfer of the test installer.
2. Sunday: perform the pilot and clean-account exercise; retain errors and assistance.
3. After Dilip reports a successful clean-account install: review and integrate
   **#18 → #19 → #20, then #15/#16**, each on its exact green head. Preserve ancestry
   and keep main green. Approval is conditional; no merge happens merely because
   this packet or automated test exists.
4. Finalize researcher Studio and the example-document navigation,
   rebuild **one frozen installer**, then accept both journeys on its exact bytes.
   Record real documents/answers/receipt behavior and real Studio Qwen/Granite
   inference, evaluation, recovery and export. Preserve quality failures. Any code
   fix requiring a rebuild creates a new candidate/hash and repeats both acceptances.
5. Deliver the final private package and evidence by December 4 end of day. Hosted
   Ubuntu CI is the accepted Linux gate; do not change Docker Desktop settings.
   Publication requires a **separate owner message naming the exact installer
   SHA-256**, after acceptance. The deadline does not authorize publication.
