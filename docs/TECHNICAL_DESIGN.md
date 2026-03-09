# ColabMusic — Technical Design Reference

## Data Models Summary

### accounts app
- **UserProfile**: OneToOne(User), display_name, bio, avatar, roles(M2M), genres(M2M), reputation_score
- **Role**: name (LYRICIST|PRODUCER|VOCALIST), display_name, description, icon
- **Genre**: name, slug, parent(self FK for sub-genres)
- **Badge**: name, condition, description, icon
- **UserBadge**: user(FK), badge(FK), awarded_at

### projects app
- **Project**: title, slug, description, project_type(ORIGINAL|COVER), status(state machine), genre(FK), tags(M2M), created_by(FK), is_public, allow_multiple_versions
- **Lyrics**: project(FK), author(FK), content, language, is_selected, original_artist(for covers), original_song(for covers)
- **Beat**: project(FK), producer(FK), [AudioMixin fields], bpm, key_signature, description, is_selected
- **VocalTrack**: project(FK), vocalist(FK), [AudioMixin fields], description, is_selected, version_number
- **FinalMix**: project(1to1), [AudioMixin fields], lyrics(FK), beat(FK), vocal_track(FK), cover_image, play_count, is_featured

### rankings app
- **Vote**: user(FK), content_type(FK), object_id, vote_type(UPVOTE|DOWNVOTE) — uses Generic FK
- **RankingCache**: ranking_type, period, genre(FK null), role(FK null), entries(JSON), calculated_at
- **ReputationLog**: user(FK), points, reason, created_at

### notifications app
- **Notification**: recipient(FK), sender(FK null), notification_type, title, message, is_read, link, created_at

## Reputation Points

| Action | Points |
|--------|--------|
| Upvote received | +10 |
| Downvote received | -2 |
| Song completed | +50 |
| Top 10 weekly | +100 |
| First accepted contribution | +25 |

## Project Status Flow

```
ORIGINAL:  SEEKING_LYRICS → SEEKING_BEAT → SEEKING_VOCALS → IN_REVIEW → COMPLETE
COVER:     SEEKING_BEAT → SEEKING_VOCALS → IN_REVIEW → COMPLETE
Any state → ARCHIVED (by creator only)
```

## URL Structure

```
/                           → Homepage (trending, recent)
/accounts/
  /login/                   → Login (allauth)
  /signup/                  → Register
  /profile/<username>/      → Public profile
  /settings/                → Edit profile
/projects/
  /                         → Browse/search projects
  /new/                     → Create project
  /<slug>/                  → Project detail
  /<slug>/edit/             → Edit project (owner only)
  /<slug>/lyrics/submit/    → Submit lyrics
  /<slug>/beats/submit/     → Submit beat
  /<slug>/vocals/submit/    → Submit vocal track
  /<slug>/select/<type>/<id>/ → Select contribution
  /<slug>/finalize/         → Create final mix
/covers/
  /                         → Browse covers
  /new/                     → Create cover project
/rankings/
  /                         → Global rankings
  /trending/                → Trending now
  /by-role/<role>/          → Rankings by role
  /by-genre/<genre>/        → Rankings by genre
  /covers/                  → Cover rankings
/search/
  /                         → Search page
  /results/                 → HTMX search results partial
/api/
  /waveform/<track_id>/     → Waveform JSON data
  /audio/status/<id>/       → Audio processing status (HTMX polling)
```

## Environment Variables Required

```
SECRET_KEY=django-secret-key
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/colabmusic
REDIS_URL=redis://localhost:6379/0
S3_BUCKET_NAME=colab-music
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
ALLOWED_HOSTS=localhost,127.0.0.1
```
