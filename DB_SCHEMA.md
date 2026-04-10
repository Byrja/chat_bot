# MD4 DB Schema (MVP draft)

## users
- id INTEGER PK
- tg_user_id INTEGER UNIQUE NOT NULL
- username TEXT
- first_name TEXT
- created_at DATETIME

## applications
- id INTEGER PK
- tg_user_id INTEGER NOT NULL
- status TEXT NOT NULL  -- draft|submitted|approved|rejected
- submitted_at DATETIME
- decided_at DATETIME
- decided_by_admin_id INTEGER
- reject_reason TEXT
- invite_link TEXT
- invite_expires_at DATETIME
- invite_uses_limit INTEGER DEFAULT 1
- created_at DATETIME
- updated_at DATETIME

## application_answers
- id INTEGER PK
- application_id INTEGER NOT NULL
- question_code TEXT NOT NULL
- answer_text TEXT NOT NULL
- position INTEGER NOT NULL
- created_at DATETIME

## moderation_events
- id INTEGER PK
- application_id INTEGER NOT NULL
- action TEXT NOT NULL -- submit|approve|reject|invite_generated
- actor_tg_user_id INTEGER
- meta_json TEXT
- created_at DATETIME

## sanctions
- id INTEGER PK
- target_tg_user_id INTEGER NOT NULL
- action TEXT NOT NULL -- warn|mute|ban
- reason TEXT
- until_at DATETIME
- issued_by_tg_user_id INTEGER NOT NULL
- created_at DATETIME

## limits
- daily apply limit: max 2 submitted applications per tg_user_id per UTC day
