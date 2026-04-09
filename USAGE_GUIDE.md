# Dance Archive Video CMS - Usage Guide

## Getting Started

### 1. Create a Superuser (First Time Only)
```bash
uv run python manage.py createsuperuser
```

### 2. Start the Server
```bash
uv run python manage.py runserver
```

### 3. Access the Admin Interface
Go to: **http://localhost:8000/admin/**

## Video Upload & Clipping Workflow

### Step 1: Upload a Video
1. **Go to Admin**: http://localhost:8000/admin/
2. **Click "Videos"** in the Archive section
3. **Click "Upload Video"** button (top right)
4. **Fill out the upload form**:
   - **Video file**: Select your video file
   - **Title**: e.g., "VHS Tape #47 - Mixed 1980s Content" 
   - **Description**: What you know about the content
   - **Source format**: VHS, Betamax, Digital, etc.
   - **Source location**: Where you found it
   - **Estimated date range**: e.g., "1987-1990"
5. **Click "Upload Video"** - this will upload to Cloudflare Stream
6. **Wait for processing** - video status will change from "Processing" to "Ready"

### Step 2: Create Clips with Video Player
1. **Go to Videos list** in admin
2. **Find your uploaded video** (status should be "Ready")
3. **Click "Create Clips"** button in the Clipping column
4. **Use the integrated video player**:
   - **Play the video** and watch for content
   - **Click "Set Start Time"** when you find the beginning of a clip
   - **Click "Set End Time"** when you reach the end
   - **Click "Preview Clip"** to test your selection
5. **Fill out clip metadata**:
   - **Title**: e.g., "Giselle Act I - Mad Scene"
   - **Content type**: Performance, Rehearsal, Class, etc.
   - **Piece**: Link to a choreographic work
   - **Performance**: Link to specific performance
6. **Click "Create Clip"** to save

### Step 3: Manage and Edit Clips
- **View existing clips** at the bottom of the clipper page
- **Click "Jump to Clip"** to preview existing clips
- **Edit clips** by clicking their titles
- **Add performers** and detailed metadata in the clip edit page

## Setting Up Supporting Data

### Before Clipping, You'll Want:
1. **People** (Dancers, Choreographers)
   - Go to Archive → People → Add Person
   - Add names, roles, bio info

2. **Companies** (Ballet Companies, etc.)
   - Go to Archive → Companies → Add Company
   - Add company names, locations, types

3. **Venues** (Theaters, Studios)
   - Go to Archive → Venues → Add Venue
   - Add theater names, cities, capacity

4. **Pieces** (Ballets, Choreographic Works)
   - Go to Archive → Pieces → Add Piece
   - Add ballet titles, choreographers, years

5. **Performances** (Specific Shows)
   - Go to Archive → Performances → Add Performance
   - Link pieces, venues, companies, dates
   - Add cast information

## API Endpoints

The system also provides REST API endpoints:

- **Videos**: `/api/videos/`
- **Clips**: `/api/clips/`
- **People**: `/api/people/`
- **Pieces**: `/api/pieces/`
- **Companies**: `/api/companies/`
- **Venues**: `/api/venues/`
- **Performances**: `/api/performances/`

## Cloudflare Stream Setup

To enable video uploads, you need Cloudflare Stream credentials:

1. Copy `.env.example` to `.env`
2. Add your Cloudflare credentials:
   ```
   CLOUDFLARE_ACCOUNT_ID=your_account_id
   CLOUDFLARE_API_TOKEN=your_api_token
   ```

## Typical Archivist Workflow

1. **Set up basic data** (people, companies, pieces)
2. **Upload raw video** (full tapes/files)
3. **Review and identify content** 
4. **Create clips** with rich metadata
5. **Link clips to performances** and cast information
6. **Add archival notes** and verification status

The system is designed for professional archival workflows with rich dance-specific metadata!