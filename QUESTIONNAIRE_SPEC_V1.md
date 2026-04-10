# MD4 Questionnaire Spec v1

Status: draft from owner input (2026-04-10)

## Intake fields
1. `name` (text)
   - Prompt: `Как тебя зовут?`

2. `tg_handle` (auto)
   - Source: Telegram profile (`@username` if exists, else numeric user id)
   - Prompt: none (auto-collected)

3. `district` (text)
   - Prompt: `Расскажи, где живешь? (район проживания) 🏠`

4. `age` (number)
   - Prompt: `Сколько тебе лет? 🔞`
   - Validation: integer 14..99 (configurable)

5. `hobby` (long text)
   - Prompt: `Поделись, чем занимаешься в свободное время, может у тебя есть мегакрутое хобби и у тебя найдутся приятели по интересам? 🧬`

6. `alcohol` (select)
   - Prompt: `Как относишься к алкоголю? 🍺`
   - Options: `Да` / `Нет` / `За компанию`

7. `availability` (text)
   - Prompt: `Как часто у тебя есть свободное время и сможешь ли посещать наши сходки?`

8. `photo` (telegram file_id)
   - Prompt: `Прикрепи фотографию, чтобы мы знали, с кем нам предстоит дружить!`
   - Validation: must be photo attachment

## Final user message after questionnaire submission
`После рассказа о себе, я добавлю тебя к ребятам 😊 Приятного времяпрепровождения ❤️`

## Review step (mandatory)
Before sending to admins, bot shows full preview card with inline buttons:
- `✏️ Редактировать`
- `✅ Отправить`

## Admin decision
- `✅ Одобрить`
- `❌ Отказать` (optional reason supported)

## Approve path
- Create unique invite link for main chat:
  - `member_limit=1`
  - `expire_date=now+24h`
- Send invite only in user's private chat.

## Reject path
- Send rejection notice to user.
- Reapply allowed.

## Limits
- max 2 submitted applications per UTC day per user.
