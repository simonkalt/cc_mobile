Just created this new branch to embark on a Super User Admin web portal.  Only users with super_user=true in the db have access to this portal (I just added the field at the root level of the users table).

Since this is very sensitive (all our data), I want to use 2FA leveraging our verification system defaulting to SMS (Email as the other option).

Once successfully logged in we will see a standard grid with filter and sortable headers for the following fields: name, email, phone, isActive, lastLogin, subscrptionStatus.

We can do a paging type grid to fill the page using prev and next arrows with record count following.

I want it in the theme of our website.

When we hover over a row (user record), I want it to highlight. When we click on the row, keep the hightlight and open a details modal.  Here we will do simple CRUD activity. We can Edit and Archive the user from here.  NO DELETING to keep history, just Archiving (new root field called archived (bool).

