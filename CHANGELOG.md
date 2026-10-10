# Changelog

What changed in Alice, newest first. One line per pull request: what changed for Stefan, and "You need to: …" when
there is a manual step. Every pull request that changes code adds its line under the day's date (see CLAUDE.md); the
pull request check fails without it. At each deploy Alice reads this file: Admin › What's new shows it, and each release
becomes a knowledge item in the category "Alice changes".

## 2026-10-10

- #46 Digital teams: the Members tab shows each member's cost for the last 7 days, this month, last month, the last 12 months and all time, with the model's tier, jobs worked and the team's cost per job. The default pricing template per client is now a team setting (Knowledge tab: Add, Change, Remove), no longer on the organisation's page; Start a job uses the client's, then the team's, then Alice's own layout. You need to: on your Quantity surveying team's Knowledge tab, Preview the move of the old organisation defaults, then Confirm it.
- #44 No rule is fixed in code (D-0045): rule defaults live in a config file each deployment can override; Core rules need an Owner and a reason, and every rule change can be reverted (Rules › Changes). "Human approval" is now "Approval and library management" (D-0044): who approves, what Temple may do, no overwrite or delete, what waits for a person. Temple's actions are on Activity with Undo; Actions lists only what waits for you. You need to: check the new rule (supersede is on), and upload the Copilot package 1.3.0 when convenient.
- #43 Temple routes each new item to the right space (work to the team, general to the Organisation space, about you to your personal space, about a named person to the team's restricted space, unsure to you), restricted spaces for casework, and approval goes to each space's managers (you see a count). You need to: back up data\ on the PC first; make HR casework on Spaces, set it on the HR card and add it to the HR-Team group mapping.
- #42 Open by default: an Organisation space everyone reads (organisations, general knowledge and decisions belong there; facts from internal sources stay in their team's space), team spaces readable across the organisation unless a manager closes them, Entra groups mapped to spaces and a profile, and a Team member profile. You need to: back up data\ on the PC first; add the groups claim to the web sign-in app in Entra; then preview and confirm the move on Spaces, and close Stefan: work if it should stay members only.
- #41 Work items no longer get stuck in personal spaces: the sharing check waits for Temple's review and holds only an actual finding; Temple's category is enough for work items; new items go to each person's team space by default; Actions lists work items in personal spaces to move; an Owner can link a person's accounts. You need to: back up data\ on the PC first; then link your Tuduma admin account to your everyday account on Users and permissions.

## 2026-10-09

- #40 /signed-out is now a "Sign in to Alice" page to bookmark: Alice's look, a secure-connection badge showing the address you are really on, one Sign in with Microsoft button (it clears this browser's old sign-in first) and a note on what to check; no fields to type into, and the signed-out messages still show when they apply.
- #38 Hand over a departing person's work: once someone is suspended (or has lost their Alice role), an Owner can see their personal-space items by title on Users and permissions, open one to read it, and move only the ticked ones into a shared space they manage; each goes through the sharing check, anything held is explained on Actions for you to share with a reason or keep, and nothing is deleted. You need to: on the PC, back up data\ before updating (two columns are added); in Azure the database backups cover it.
- #39 Tests on GitHub no longer fail before they start when Docker Hub refuses the download: Docker's official images now come from Amazon's public copy of them (the same images). Also fixes the Spaces test that sometimes stopped with "database is locked" (Alice no longer looks up a member's name while still reading the members list). You need to: copy deploy/github/deploy.yml over .github/workflows/deploy.yml.
- #37 Purview labels are now read the same whichever program wrote an Office file, so a Word, Excel or PowerPoint file with a blocked label is always refused (before, an Excel file written with one common library slipped through).
- #36 Digital teams: drawings are read as images (dimensions, levels, notes, scale and drawing number, each citing its page, with the cost shown per member and on the job), a team setting for when information is missing (Ask me, or Assume and flag with every assumption listed in the outputs), and files can be added to a job that has started, re-running only the work that depends on them. You need to: to use Assume and flag on your existing Quantity surveying team, choose it on the team's Rules and autonomy tab (new teams from the template start on it).
- #35 Digital teams: the Members tab is now a card per member in hand-off order, with each member's cost for the period you choose, warnings where a member is set up to fail, an editor in the side panel (with what changed in its instructions), Add a member from a template, and drag or keyboard reordering.
- #34 A change log: this file, Admin › What's new (the running release, when each release went live, and the setup steps run in Azure), a knowledge item per release in "Alice changes", and Ask Temple can say what changed recently. You need to: copy deploy/github/deploy.yml over .github/workflows/deploy.yml, so pull requests are checked for their change log line.
- #33 Every memory is checked on its own before any model sees it: one that fails the rules is left out and logged, and the rest still go.
- #32 Quantity surveying: provisional sums, exclusions with a reason, and no item is left unpriced without your decision.
- #31 Temple's model for screening and categories can be Cloud or Local (a small model inside your own Azure environment), with an evaluation to compare them. You need to: only to try Local, run azure-setup.ps1 -Step localmodel -LocalModel on, then Run the evaluation on the Agents page.
- #30 Quantity surveying: a stopped job can be resumed as a new version, a template can be removed from a team's list, and macro-enabled templates keep their macros.
- #24 Spaces: everyone has a personal space, and shared spaces have named members and a sharing check before anything goes in.
- #29 The team costs test no longer fails by chance; no change to Alice itself.
- #28 -Step users works on Windows PowerShell 5.1 (the app roles JSON). You need to: run -Step users -OwnerObjectId f955e821-… -AdminObjectIds e610cc9b-… again, then -Step apps, then sign in again.
- #27 Entra decides who owns Alice (the Alice.Owner role); the Backup page is in the menu and reads the backup vault correctly. You need to: run -Step users -OwnerObjectId f955e821-… -AdminObjectIds e610cc9b-…, then -Step apps, then sign out of Alice and in again.
- #26 Fixed the role ID that stopped -Step backup, and the setup script never deploys without the database address. You need to: run -Step backup, then -Step check.
- #25 The setup script keeps its state in Azure, rebuilds it from what is deployed, and has a read-only -Step check. You need to: from the merged code, run -Step check, then -Step users.

## 2026-10-08

- #23 Users, roles and section permissions: Owner, Admin and Member, each with a permission profile. You need to: run -Step users; to let Entra app roles decide who gets in, -Step users -UseAppRoles on, then -Step apps.
- #22 Digital teams: pricing templates (your own spreadsheets, filled in for each job) and the Start a job screen.
- #21 Digital teams: running costs by member and job, re-pricing chosen items, and job versions. You need to: rebuild and upload the Copilot package (1.2.9).
- #20 Backups: the restore runbook, a restore drill (button, workflow and monthly) and recovery targets on the Backup page. You need to: copy deploy/github/deploy.yml and restore-drill.yml into .github/workflows, then run -Step backup again.
- #19 Backups: daily file share snapshots, a lock on the resource group, a nightly off-site copy in UK West, and the Backup page. You need to: copy deploy/github/deploy.yml into .github/workflows, then run -Step backup.
- #18 Quantity surveying: Market Trends looks at current market costs, and the team files a summary of finished work in Knowledge.
- #17 Quantity surveying: team estimates when you allow them, and no more repeated questions or send-back loops.
- #16 Quantity surveying: long jobs work in parts, and an answer the team cannot read is explained instead of failing.
- #15 Organisations: see exactly what Temple starts from before it researches or scans, and add an organisation with its first guidance in one form.
- #14 A provider errors test that sometimes failed on PostgreSQL is fixed; no change to Alice itself.

## 2026-10-07

- #13 Digital teams: new pages for all teams, one team and one job.
- #12 Client material follows the Rules page: a new rule, "Client-facing documents use only that client's material", and team jobs follow Client separation.
- #11 Temple explains what organisation research and opportunity scans found and why, and you can steer them with your own guidance.
- #10 Digital teams, first phase: the team framework and a quantity surveying team that produces a cost estimate as a Word cost plan and an Excel workbook.
- #9 Parker page: Set-up stays with the form, above a written proposal's draft.
- #8 A failed model call now shows the provider's own reason everywhere, not just the error's name.
- #7 Web search keeps the provider's own error, OpenAI web search works again, and a refused search tries the other provider.
- #6 Parker: Apply and Check again save on a written proposal, and suggestions whose changes were lost can be applied again.
- #5 Parker: no more Format and flow (a proposal's sections come from its template), and the draft shows as one document you can edit in place. You need to: if you use Alice in Copilot, rebuild and upload the Copilot package (1.2.8).
- #4 Parker groups proposals into bids with versions: a new version replaces the old one, which becomes read-only, and waiting suggestions move across. You need to: rebuild and upload the Copilot package.
- #3 The morning sign-in loop is fixed: the old service worker is retired, and "Trouble signing in?" on the signed-out page resets sign-in on that device.

## 2026-10-06

- #2 The Rule packs page looks and works like the Rules page.
- #1 Parker greets you with "Hello, I'm Parker", and the Proposals list is clearer.
