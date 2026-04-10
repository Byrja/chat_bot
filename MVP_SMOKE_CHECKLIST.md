# MD4 MVP Smoke Checklist

Date: __________
Tester: __________

## User flow
- [ ] `/start` opens questionnaire
- [ ] Steps 1-4 accept valid inputs and reject invalid age
- [ ] Step 5 alcohol buttons work (`Да/Нет/За компанию`)
- [ ] Step 6 free-text availability saved
- [ ] Step 7 photo required and accepted
- [ ] Preview shown with `Редактировать / Отправить`
- [ ] `Редактировать` returns to question 1
- [ ] `Отправить` changes status to submitted

## Limits
- [ ] 3rd submit in same UTC day is blocked (limit 2/day)

## Admin moderation flow
- [ ] Submitted application appears in admin chat
- [ ] `Одобрить` sends one-time invite link to user
- [ ] Invite has TTL 24h and single-use limit
- [ ] `Отказать` asks for optional reason
- [ ] Reject with reason reaches user
- [ ] Reject with '-' works without reason

## Access control
- [ ] Non-admin cannot use moderation callbacks

## Pass criteria
- [ ] No dead-ends in callbacks
- [ ] No unhandled exceptions in logs
- [ ] Core flow works end-to-end
