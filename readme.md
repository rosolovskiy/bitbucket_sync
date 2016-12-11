# Bitbucket_sync.py #

Script for automatic backup copy of the all repositories available
to the script (based on OAuth permissions).

## Requirements ##
* Python <code>requests</code> library
* Python 2.7+
* git 1.6.5+

## OAuth setup ##
This is required to grant read access for script to your repositories.
1. Log in to bitbucket using account you want to back up
1. Go to Bitbucket settings (in your profile)
1. In **Access Management** choose **OAuth** configuration page
1. Click **Add Consumer** and fill the form
   1. Any name, example: *Bitbucket Sync*
   1. Callback URL can be any url, since we are not using OAuth authorization based on code exchange
   1. Check **This is a private consumer**
   1. Required permissions are: **Account.Read, Team membership.Read, Projects.Read, Repositories.Read**
   1. Click Save and go back to **OAuth** configuration page
1. Click on your new consumer and you will see **Key** and **Secret** credentials, remember them, we will need them to start the script. That's it!

## Installation ##
You can set up <code>requests</code> library manually, using <code>pip install requests</code> command.
If you system uses <code>virtualenv</code>, then you can create your virtual environment and target pip to <code>requirements.txt</code> file:
1. <code>cd <path_where_you_store_virtual_env</code>
1. <code>virtualenv bitbucket_sync_virtualenv</code>
1. <code>source bitbucket_sync_virtualenv/bin/activate</code>
1. <code>cd path/to/bitbucket_sync/</code>
1. <code>pip install -r ./requirements.txt</code>

Make sure that when you run the script the virtualenv is activated.

## Run example ##
<code>python bitbucket_sync.py "/home/user/projects_backup" OauthKey oAutHsEcrEt</code>