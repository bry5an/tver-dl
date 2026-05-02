# Ansible Playbook: Copy Files to Remote Server

This playbook syncs files from local subdirectories to matching paths on a remote Ubuntu server over SSH, then cleans up the local files.

## Setup

### Prerequisites

- **Ansible** installed on your control machine (macOS, Linux, etc.)
- **rsync** installed on both the control machine and the remote Ubuntu server
- SSH access to the remote server with key-based or password authentication

### Inventory Configuration

Edit `ansible/hosts` to define your remote server:

```ini
[media-server]
media  # hostname or IP address of your Ubuntu server

[media-server:vars]
ansible_host=192.168.1.100  # IP address or hostname
ansible_user=bryan           # SSH user (optional, defaults to current user)
ansible_port=22              # SSH port (optional, defaults to 22)
```

## Usage

### Basic Run

To execute the playbook with default settings:

```bash
cd /Users/bryan/git/tver-dl
ansible-playbook ansible/site.yml -i ansible/hosts
```

### Custom Paths

Override the local and remote base directories:

```bash
ansible-playbook ansible/site.yml -i ansible/hosts \
  -e "local_base=/custom/local/path remote_base=/custom/remote/path"
```

### With SSH Key

If your SSH key is not in the default location:

```bash
ansible-playbook ansible/site.yml -i ansible/hosts --private-key=/path/to/key
```

### Verbose Output

For detailed logs:

```bash
ansible-playbook ansible/site.yml -i ansible/hosts -v
```

## Configuration

### Default Paths

Edit `ansible/roles/copy_files/defaults/main.yml`:

```yaml
local_base: "/Users/bryan/Video/Kids_shows/source"
remote_base: "/mnt/media/TV/source"
```

These paths are used if not overridden via command-line.

## How It Works

1. **Find** all direct subdirectories in `local_base`
2. **Sync** each subdirectory's contents to `remote_base/<subdirectory_name>/` using rsync
3. **Delete** local subdirectories after successful transfer

### Example Directory Structure

**Local:**
```
/Users/bryan/Video/Kids_shows/source/
├── show_1/
│   ├── episode_1.mp4
│   └── episode_2.mp4
├── show_2/
│   └── episode_1.mp4
```

**Remote (after playbook runs):**
```
/mnt/media/TV/source/
├── show_1/
│   ├── episode_1.mp4
│   └── episode_2.mp4
├── show_2/
│   └── episode_1.mp4
```

**Local (after cleanup):**
```
/Users/bryan/Video/Kids_shows/source/
(empty)
```

## Playbook Structure

```
ansible/
├── README.md                          # This file
├── site.yml                           # Main playbook (minimal)
├── hosts                              # Inventory file
└── roles/
    └── copy_files/
        ├── defaults/main.yml          # Default variables
        ├── vars/main.yml              # Role-specific variables
        └── tasks/main.yml             # Copy & cleanup tasks
```

## Troubleshooting

### "rsync not found"
Install rsync on both machines:
```bash
# On macOS (control machine)
brew install rsync

# On Ubuntu (remote server via SSH)
ssh user@host sudo apt-get install rsync
```

### Unicode/UTF‑8 errors when scanning local files
If any of your local subdirectory names contain non‑ASCII characters you may see
an error like:
```
Refusing to deserialize an invalid UTF8 string value: 'utf-8' codec can't encode character ...
```
This happens because the control node returns a path that Ansible's JSON
serializer deems invalid. The easiest fix is to disable the strict UTF-8 check
in your configuration. A sample `ansible/ansible.cfg` is provided with:

```ini
[defaults]
module_strict_utf8_response = False
```

Alternatively set the environment variable when you run the playbook:

```bash
ANSIBLE_MODULE_STRICT_UTF8_RESPONSE=0 ansible-playbook ansible/site.yml -i ansible/hosts
```

After doing so the play should proceed even if directory names include
Japanese, emoji, or other exotic characters.


### "Permission denied"
Ensure the SSH user has write permissions on the remote base directory:
```bash
ssh user@host ls -ld /mnt/media/TV/source
```

### "No such file or directory"
Verify the local and remote paths exist:
```bash
# Local
ls -d /Users/bryan/Video/Kids_shows/source

# Remote via SSH
ssh user@host ls -d /mnt/media/TV/source
```

## Notes

- The playbook **deletes local files only after successful sync**
- Use `-v` flag for detailed debugging
- Test with a small directory first before running on large datasets
