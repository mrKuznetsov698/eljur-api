# Eljur protocol reference

This document describes the request and response contracts used by the SDK. Availability and permissions can vary between schools.

## Origins and common parameters

School API: configured school HTTPS origin, by default `https://<vendor>.eljur.ru`. School directory: `https://global.eljur.ru`. Configure school hostname and `vendor` independently for custom domains.

Eljur requests use `devkey` and `vendor`; v3 uses `out_format=json`. Authenticated v3 and control-work calls carry `auth_token` as a query parameter. The SDK uses a configurable User-Agent and accepts an optional Cookie header for school requests.

## Endpoint map

Common parameters above are omitted from the table.

| HTTP | Path | Additional query/body |
| --- | --- | --- |
| POST | `/apiv3/auth` | JSON `login`, `password`; no auth_token |
| GET | `/api/schools/mobileapp` | `value` |
| GET | `/apiv3/getrules` | None |
| GET | `/apiv3/getperiods` | `weeks`, `show_disabled`: lowercase booleans |
| GET | `/apiv3/getdiary` | `student`, `days`, `rings` (main diary uses integer `1`) |
| GET | `/apiv3/getmarks` | `student`, `days` |
| GET | `/apiv3/getfinalassessments` | Optional `student` (year-results variant supplies it) |
| GET | `/apiv3/getmessages` | `folder`, `unreadonly`, `limit`, `page`, optional `filter` |
| GET | `/apiv3/getmessageinfo` | `id` |
| GET | `/apiv3/getmessagereceivers` | None |
| POST | `/apiv3/sendmessage` | Query `id`; JSON `subject`, `text`, `users_to`, `fid`, `filename` |
| GET | `/apiv3/getboardnotices` | `limit`, `page` |
| GET | `/apiv3/getboardnoticeinfo` | `id` |
| GET | `/journal-cw-ajax-action` | `method=cw.get_by_student_id`, `student_id`, `dateStart`, `dateEnd`, `lesson_id` |
| POST | Dynamic URL from `getrules.result.uploadFileUrl` | Multipart field `userfile`; file bytes, filename, MIME type |

Message defaults: `unreadonly=no`, `limit=20`, `page=1`. The SDK's `unread_only=True` maps to `yes`; this non-default value is an inference and requires live verification. Supported `folder` values are `inbox` and `sent`. `filter` is passed unchanged. Announcement defaults: `limit=20`, `page=1`. The SDK leaves pagination to callers.

Recipient user IDs are joined with commas in `users_to`. Each uploaded file ID in `fid` has a corresponding name in `filename`. The query `id` identifies the sender's account/person, not a reply-message ID; callers must supply it explicitly. Upload success requires `success=true` and nonempty `file`/`name` strings.

## Response envelopes

API v3:

```json
{"response":{"state":200,"error":null,"result":{}}}
```

Login requires application `state=200` and returns `result.token` and `result.expires`. HTTP 200 alone does not establish success. `expires` is modeled as a string; its interpretation is unverified and the SDK preserves it without automatic refresh.

Non-v3 responses:

| Route | Top-level response fields |
| --- | --- |
| School directory | `result` boolean, `options` array, `error` string |
| Control works | `rows` array, `datesState` object, `error`, `is_lms_control_works_available` |
| File upload | `state`, `success`, `file`, `url`, `name`, `error`, `error_code` |

Error mapping of state/HTTP 401 and 403 to `AuthenticationError` and 429 to `RateLimitError` is SDK policy. The full set of production error states is unverified. Other non-200 states raise `APIError`; malformed envelopes raise `ProtocolError`.

## Observed result shapes

These field paths describe the response structures supported by the SDK; they have not been validated against authenticated live responses. Fields can be null, omitted, or differ across schools. The client returns JSON to preserve differences.

| Result | Observed structure |
| --- | --- |
| Rules/profile | `id`, `name`, `firstname`, `lastname`, `roles`, `vendor`, `relations.students` map, `relations.groups` map, `uploadFileUrl`, school and support details |
| Related student | Map key is student ID; fields include `name`, `title`, `class`, `parallel`, `firstname`, `lastname`, `rules` |
| Periods | `students` array → `periods` array → `weeks` array, with `start`, `end`, `title` |
| Diary | `students` map → `days` map → `items` map and `items_extday` array |
| Lesson | `name`, `num`, `lesson_id`, `teacher`, `room`, `starttime`, `endtime`, `topic`, `homework`, `assessments`, `files`, `resources` |
| Homework | Main diary uses a map of entries with `id`, `individual`, `value`; extra-day homework is generic JSON |
| Diary file | `filename`, `link`, `toid`; other representations may use `id`, `name`, `url` |
| Marks | `students` map → `lessons` array → `marks` array; lesson has `average`, `average_convert`, `lesson_id` |
| Mark | `value`, `date`, `weight`, `weight_float`, `count`, `countas`, `comment`, `lesson_comment`, `mtype` |
| Final assessments | `students` map → `items` array → `assessments` array; assessment has `period`, `value`, `convert`, `comment` |
| Messages | `count`, `total`, `messages` array; each includes `id`, `date`, `subject`, `short_text`, `unread`, `user_from`, `users_to` |
| Receivers | `groups` array → `users` / `subgroups` arrays; recipient ID is serialized as `name`, alongside `firstname`, `lastname`, `search`, `info` |
| Notices | `count`, `total`, `total_unread`, `notices` array |
| Notice detail | `notice` object including `text`, `files`, `user_from`, `date_actual_before` |

No grade-average computation is added: the server supplies averages and assessment weighting can vary by school.

## What remains unverified

Authenticated requests have not been run. Permissions and availability depend on account role and school. The control-work date format and web-cookie requirements require live verification. SSO/ESIA, token refresh/revocation, unread side effects, production rate limits, and other routes outside this SDK are not implemented or promised. Tests validate wire serialization and failure handling against synthetic fixtures, not server availability.
