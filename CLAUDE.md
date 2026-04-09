# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a **Django-based Video Content Management System** specifically designed for dance archives. The system integrates with Cloudflare Stream for video hosting and provides rich metadata management for ballet and dance performances.

## Development Commands

### Environment Setup
- Install dependencies: `pip install -r requirements.txt`
- Copy environment file: `cp .env.example .env` (then edit with your Cloudflare credentials)
- Create superuser: `uv run python manage.py createsuperuser` 
- Run migrations: `uv run python manage.py migrate`

### Development Server
- Start development server: `uv run python manage.py runserver`
- Access admin interface: http://localhost:8000/admin/
- API endpoints available at: http://localhost:8000/api/

### Database Management
- Make migrations: `uv run python manage.py makemigrations`
- Apply migrations: `uv run python manage.py migrate`
- Django shell: `uv run python manage.py shell`

## Architecture Overview

### Core Models (archive/models.py)
The system follows a hierarchical dance metadata structure:

**Content Hierarchy:**
- `Video` → Raw archival videos uploaded to Cloudflare Stream
- `Clip` → Time-segmented portions of videos with rich metadata

**Performance Context:**
- `Performance` → Specific shows/events with date, venue, company
- `PerformanceCast` → Junction table linking performers to roles in performances
- `Piece` → Choreographic works / dance works (ballets, etc.). Displayed as "Dance Work" in frontend and admin UI.
- `Person` → Dancers, choreographers, conductors
- `Company` → Ballet companies, dance troupes
- `Venue` → Theaters, studios, performance spaces

### Key Technical Integration
- **Cloudflare Stream**: Video hosting and streaming (archive/utils/cloudflare.py)
- **Django REST Framework**: API endpoints for all models
- **Custom Admin Interface**: Specialized video clipper tool with embedded player

### Admin Interface Features
- **Video Upload**: Direct upload to Cloudflare Stream via admin
- **Video Clipper**: Custom tool for creating time-based clips with metadata
- **Rich Metadata Forms**: Dance-specific fields (roles, movements, archival confidence)

### API Structure
All models expose REST endpoints at `/api/`:
- Videos, clips, people, pieces, companies, venues, performances, cast

### File Organization
- `archive/` - Main Django app containing all models, views, admin
- `video_cms/` - Django project settings and main URL configuration
- `archive/templates/admin/` - Custom admin templates for video clipper
- `archive/utils/` - Cloudflare Stream integration utilities

## Environment Configuration
Required environment variables (see .env.example):
- `CLOUDFLARE_ACCOUNT_ID` - For video upload/streaming
- `CLOUDFLARE_API_TOKEN` - API authentication
- `SECRET_KEY` - Django security
- `DEBUG` - Development mode flag

## Custom Fields / Taxonomy System

The CMS has a generic metadata system that lets admins create arbitrary fields (like "Genre") and attach them to any entity (Piece, Clip, etc.) without schema changes.

### How it works

Three models power the system:

1. **FieldType** — A lookup table of field kinds (e.g., "choice", "text", "number"). Must be pre-populated in Admin > Field Types before creating custom fields. *(Note: this model is arguably unnecessary indirection — see DVNY-35.)*

2. **CustomField** — A field definition. Example: a "Genre" field of type "choice" with choices `["Ballet", "Modern", "Duncan"]`, applicable to entity types `["piece", "clip"]`.

3. **CustomFieldValue** — An actual value attached to a specific object via Django's generic foreign key (ContentType + object_id). Example: Piece #5 has Genre = "Ballet".

### Admin workflow: adding a new taxonomy

1. **Create a FieldType** (if needed): Admin > Field Types > Add. Enter "choice" as the name.
2. **Create a CustomField**: Admin > Custom Fields > Add.
   - Name: `Genre`
   - Field type: `choice`
   - Entity types: check `piece` (and any others)
   - Choices: `["Ballet", "Modern", "Duncan"]` (JSON array)
3. **Attach values to objects**: Edit a Piece in admin. At the bottom, the "Custom Fields" inline shows a dropdown for Genre. Select a value and save.

### API usage

Custom field values are automatically included in API responses for all entities:

```json
GET /api/pieces/5/
{
  "id": 5,
  "title": "Giselle",
  "custom_fields": {
    "Genre": {
      "value": "Ballet",
      "field_type": "choice",
      "help_text": ""
    }
  }
}
```

**Filtering** by custom fields uses the `custom_` prefix:

```
GET /api/pieces/?custom_Genre=Ballet
```

This returns only pieces where the Genre custom field value is exactly "Ballet". The filter backend (`CustomFieldsFilterBackend` in `archive/views.py`) is registered on all content viewsets (Video, Clip, Piece, Person, Company, Venue, Performance).

### Frontend integration

- **Dance Work detail** (`/dance-works/[id]`): Shows genre as a clickable badge linking to `/genres/[genre]`
- **Clip detail** (`/clips/[id]`): Bubbles genre from the clip's parent dance work
- **Genre index** (`/genres`): Lists all genre choices from the Genre custom field
- **Genre detail** (`/genres/[genre]`): Shows all dance works and clips in that genre
- **Dance Works/Clips index**: Genre filter buttons in the header, driven by URL query param `?genre=Ballet`

### Key files

- `archive/models.py` — FieldType, CustomField, CustomFieldValue models
- `archive/admin.py` — CustomFieldAdmin (with checkbox widget), CustomFieldValueForm (with choice dropdown), `make_custom_field_inline()` factory
- `archive/views.py` — CustomFieldsFilterBackend, CustomFieldViewSet, CustomFieldValueViewSet
- `archive/serializers.py` — CustomFieldsMixin (adds `custom_fields` to all serializer output)
- `frontend/src/pages/genres/` — Genre index and detail pages

## Database
- Default: SQLite (db.sqlite3)
- Models use UUID primary keys for Video and Clip entities
- Supports rich archival metadata with validation confidence levels