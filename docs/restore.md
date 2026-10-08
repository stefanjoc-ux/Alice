# Restoring Alice

Four ways back, from the smallest to the largest. Run every command in **Azure Cloud Shell**, signed in to the Tuduma tenant.
Each step says which shell: **Bash** or **PowerShell**. Words in `<angle brackets>` are placeholders: replace them with your
own values. This page never contains a password or a key. Where a command needs one, it reads it from Key Vault into a variable.

A restore always goes into something **new**: a folder called `restored-…`, a new database server or a new resource group.
Live data is never overwritten. You choose when to switch Alice over, and the old copy stays until you remove it yourself.

**Find your names first** (Bash):

```
az account set --subscription <subscription id>
az resource list -g alice-rg --query "[].{name:name, type:type}" -o table
```

- `<files account>`: the storage account ending in `files`.
- `<offsite account>`: the storage account ending in `offsite` (UK West).
- `<pg server>`: the server starting `alice-pg-`.
- `<key vault>`: the vault starting `alice-kv-`.

**Targets:**
- **Recovery point:** for the database, minutes (point-in-time restore); for files, 24 hours (the daily snapshot and the nightly off-site copy).
- **Recovery time:** aim to have Alice back within 4 hours.

The Backup page shows the last restore drill's measured time against these targets.

## A. One file or folder from the file share

Use this when a document, template or image has been deleted or damaged. The share is snapshotted every day at 01:00 UK
time and each snapshot is kept for 30 days.

**In the portal:** Recovery Services vaults › `alice-backup-vault` › Backup items › Azure Storage (Azure Files) › `alice` ›
File Recovery. Pick the day, then browse to the file or folder. Choose **Alternate location** and a new folder name such as
`restored-<yyyymmdd>`.

**In Cloud Shell** (Bash):

1. List the restore points (newest first):
   ```
   az backup recoverypoint list --vault-name alice-backup-vault -g alice-rg \
     --container-name <files account> --item-name alice \
     --backup-management-type AzureStorage --workload-type AzureFileShare \
     --query "[].{name:name, time:properties.recoveryPointTime}" -o table
   ```
2. Restore one **file** into a new folder next to the original (nothing is overwritten):
   ```
   az backup restore restore-azurefiles --vault-name alice-backup-vault -g alice-rg \
     --container-name <files account> --item-name alice --rp-name <restore point name> \
     --restore-mode AlternateLocation --target-storage-account <files account> --target-file-share alice \
     --target-folder restored-<yyyymmdd> --resolve-conflict Skip \
     --source-file-type File --source-file-path "<path in the share, e.g. Documents/Policy library/leave.docx>"
   ```
   For a whole **folder**, use `--source-file-type Directory --source-file-path "<folder, e.g. Documents/Templates>"`.
3. Watch it finish:
   ```
   az backup job list --vault-name alice-backup-vault -g alice-rg -o table
   ```
4. Check the restored copy in the portal (Storage accounts › `<files account>` › File shares › `alice` › `restored-<yyyymmdd>`).
   Then move it into place yourself, and delete the `restored-` folder when you are done.

**Older than 30 days, or the snapshots are gone:** take the file from a nightly off-site copy instead (part C, steps 1 to 3).
Then unpack just that file:
```
tar -xzf files.tar.gz "alice/<path in the share>"
```

## B. The database to a point in time

Use this when data in Alice is wrong, for example after a mistake or a bad import, and you know roughly when it was last
right. Backups are kept for 35 days, and you can restore to any minute in that window. The Backup page shows "Restore from …".

1. Choose the time in UTC. UK summer time is one hour ahead of UTC. Then create a **new** server from it (Bash). It goes
   into the same private network, takes about 10 to 20 minutes, and the live server is not touched:
   ```
   SUBNET=$(az network vnet subnet show -g alice-rg --vnet-name alice-vnet -n database --query id -o tsv)
   ZONE=$(az network private-dns zone show -g alice-rg -n alice.private.postgres.database.azure.com --query id -o tsv)
   az postgres flexible-server restore -g alice-rg --name alice-pg-restored-<yyyymmdd> \
     --source-server <pg server> --restore-time "<yyyy-mm-ddThh:mm:00Z>" \
     --subnet "$SUBNET" --private-dns-zone "$ZONE"
   ```
2. The restored server is private, like the live one, so you can't look inside it from Cloud Shell. Switch at a quiet
   time (steps 3 and 4), check, and switch back if it is not right: both servers stay.
3. Switch Alice to the restored server (PowerShell). This only changes which server the `database-url` secret points to:
   ```
   $kv = '<key vault>'
   $pw = az keyvault secret show --vault-name $kv --name pg-admin-password --query value -o tsv
   $fqdn = az postgres flexible-server show -g alice-rg -n alice-pg-restored-<yyyymmdd> --query fullyQualifiedDomainName -o tsv
   $tmp = New-TemporaryFile
   [IO.File]::WriteAllText($tmp, "host=$fqdn port=5432 dbname=alice user=aliceadmin password=$pw sslmode=require")
   az keyvault secret set --vault-name $kv --name database-url --file $tmp --encoding utf-8 --output none
   Remove-Item $tmp; $pw = $null
   ```
4. Restart the live revisions so they read the new secret (Bash):
   ```
   for APP in alice-web alice-mcp; do
     REV=$(az containerapp revision list -n $APP -g alice-rg --query "[?properties.trafficWeight>\`0\`].name | [0]" -o tsv)
     az containerapp revision restart -n $APP -g alice-rg --revision "$REV"
   done
   ```
   The backup job reads the secret at its next run.
5. Check that Alice opens and shows what you expect.

6. **Make it stick.** The next time you run any setup step, add `-DatabaseHost <the restored server's address ($fqdn)>`
   once. It is remembered from then on. Without it, a setup step would point `database-url` back at the original server.

To go back, set `database-url` to the old server's address the same way (step 3) and restart again (step 4). Then run the
next setup step with `-DatabaseHost ''`.

**Keep the old server** until you are sure. While the resource group lock is on, it can't be deleted anyway.

## C. Everything, from the nightly off-site copy, into a new resource group

Use this when Alice's resource group or region is lost or unusable. The off-site copies are in UK West and are kept for
35 days. No copy can be changed or deleted, not even by you, until it is 35 days old.

1. Find the latest copy (Bash). You need Storage Blob Data Reader on `<offsite account>`; `-Step backup` gave it to the person who ran it.
   ```
   az storage blob list --account-name <offsite account> -c alice-offsite --auth-mode login \
     --query "[?ends_with(name,'-manifest.json')].name" -o tsv | sort | tail -3
   ```
2. If you want a local copy (optional), download the copy's three files:
   ```
   PREFIX=<yyyy/mm/dd/stamp, e.g. 2026/10/08/20261008T0100Z>
   for P in manifest.json database.dump files.tar.gz; do
     az storage blob download --account-name <offsite account> -c alice-offsite --auth-mode login \
       -n "$PREFIX-$P" -f "${P}" --output none
   done
   ```
3. Check them against the manifest:
   ```
   sha256sum database.dump files.tar.gz
   cat manifest.json
   ```
   The manifest also lists how many memories, knowledge items, proposals and files Alice held when the copy was taken.
4. Build a new Alice in a new resource group (PowerShell). Work in a **fresh clone**, so this has its own `azure-state.json`
   and your live setup state is never mixed with it:
   ```
   git clone https://github.com/stefanjoc-ux/Alice.git Alice-recovery
   cd Alice-recovery
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Location uksouth -Step infra
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Step secrets
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Step image
   ```
   If UK South itself is down, use `-Location ukwest`; the off-site copies are already there.
5. Load the copy into the new, empty database and file share. Do this **before** the apps start:
   ```
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Step recover -RecoverFrom <offsite account>
   ```
   - It gives the new Alice's identity read access to the off-site copies and runs the `alice-recover` job (`restore.py`).
   - The job checks each file against the manifest, loads the database in one transaction and unpacks the files. It then
     compares the counts with the manifest and fails if they differ.
   - It refuses a database that already holds tables, and a share that already holds files.
   - To restore an older copy, add `-RecoverCopy <yyyy/mm/dd>`.
6. Start the apps with sign-in:
   ```
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Step signin
   ./deploy/azure-setup.ps1 -SubscriptionId <subscription id> -ResourceGroup alice-recovered-rg -Step apps -ExtAppId <Alice API app id> -ExtCallers "<as before>"
   ```
   Then run `-Step backup`, and `-Step mail` / `-Step connector` / `-Step copilot` as you did the first time. If you use a custom
   domain, point it at the new web app, and update the GitHub variable `AZURE_RESOURCE_GROUP`.
7. Check that Alice opens and that Admin › Backups shows backups for the new resource group.

## D. Rolling back a release

Use this when a new version misbehaves. The previous revision stays switched on, so rolling back takes seconds and does not touch data.
Database changes are always additive, so the older version runs against the newer database.

- **The button:** GitHub › Actions › **Go live (promote or roll back)** › Run workflow › `rollback`.
- **From Cloud Shell** (Bash):
  ```
  git clone https://github.com/stefanjoc-ux/Alice.git && cd Alice
  RG=alice-rg bash deploy/promote.sh status
  RG=alice-rg bash deploy/promote.sh rollback
  ```
  Afterwards `status` should show the previous revision with 100% of the traffic.

## E. The restore drill

The drill proves part C works, and measures how long it takes.

- It restores last night's copy into throwaway resources in `alice-rg-drill`, and starts a temporary Alice with sign-in
  locked to you (no AI keys and no email).
- It checks that Alice starts, then compares the restored memories, knowledge items, proposals and files with the live
  counts recorded when the copy was taken.
- It then deletes every throwaway resource, even when something fails, and reports on the Backup page and by email.
- It never reads or writes Alice's live database or share.

You can start it in three ways:
- **Admin › Backups › Run a restore drill now.**
- **GitHub › Actions › Restore drill › Run workflow.**
- It also runs by itself on the 1st of each month.

It takes about 30 to 60 minutes and costs a few pence.
