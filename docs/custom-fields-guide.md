# Custom Fields Guide

This guide explains how to create and manage custom metadata (like Genre) in the Dance Visions CMS.

## What are Custom Fields?

Custom fields let you add your own categories and labels to pieces, clips, and other items in the archive -- without needing a developer to change the database. For example, you can create a "Genre" field with options like Ballet, Modern, and Duncan, then tag each piece with its genre. Those tags will automatically show up on the website.

## Quick Start: Setting Up Genres

### Step 1: Create a Field Type

Before creating a custom field, you need to tell the system what *kind* of field it is (e.g., a dropdown of choices vs. a free text box).

1. Go to **Admin > Field Types** (under the ARCHIVE section in the sidebar)
2. Click **Add Field Type**
3. Enter:
   - **Name**: `choice`
   - **Description**: `A dropdown with predefined options`
4. Click **Save**

You only need to do this once. The "choice" field type can be reused for any custom field that has a fixed set of options.

### Step 2: Create the Genre Field

1. Go to **Admin > Custom Fields**
2. Click **Add Custom Field**
3. Fill in:
   - **Name**: `Genre`
   - **Field type**: select `choice` (the one you just created)
   - **Entity types**: check the boxes for which types of items should have this field. For Genre, check **Piece** at minimum. You can also check **Clip** if you want to tag clips directly.
   - **Choices**: enter the options as a JSON list, for example:
     ```
     ["Ballet", "Modern", "Duncan", "Contemporary"]
     ```
   - **Is required**: check this if every piece must have a genre assigned
   - **Help text**: optional, e.g., `The dance style or tradition`
   - **Display order**: `0` (controls the order if you have multiple custom fields)
4. Click **Save**

### Step 3: Tag Pieces with a Genre

1. Go to **Admin > Pieces**
2. Click on a piece to edit it
3. Scroll to the bottom -- you'll see a **Custom Fields** section
4. In the **Field** dropdown, select **Genre**
5. In the **Value** dropdown, select the genre (e.g., "Ballet")
6. Click **Save**

That's it! The genre will now appear on the piece's page on the website, and visitors can browse and filter by genre.

## What Shows Up on the Website

Once you've tagged pieces with genres:

- **Piece pages**: A genre badge appears under the title, linking to the genre page
- **Clip pages**: If a clip belongs to a piece with a genre, the genre badge appears automatically
- **Genre browsing**: The `/genres` page lists all available genres. Clicking one shows all pieces and clips in that genre.
- **Filtering**: On the Pieces and Clips listing pages, filter buttons appear at the top letting visitors filter by genre

## Adding More Custom Fields

You can create additional custom fields the same way. Some ideas:

- **Era** (choice): `["Romantic", "Classical", "Neoclassical", "Contemporary"]`
- **Source** (choice): `["Live Performance", "Rehearsal", "Studio Recording"]`
- **Notes** (text): Free-form notes on a piece or clip

For free text fields, create a Field Type called `text`, then create the custom field with that type and leave the Choices field empty.

## Tips

- **Choices format**: Always use the JSON array format with square brackets and quotes: `["Option 1", "Option 2", "Option 3"]`
- **Renaming a choice**: If you need to rename a genre (e.g., "Modern" to "Modern Dance"), update the choice in the Custom Field *and* update any existing values on pieces -- the old values won't automatically change.
- **Deleting a custom field**: This will remove all values attached to all items. Be careful!
- **Display order**: If you have multiple custom fields, lower numbers appear first.
