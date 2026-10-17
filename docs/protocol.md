# Recovered protocol

This is a description of the **supplied APK**, not a claim about every deployed Eljur server. The file [apk-endpoints.json](apk-endpoints.json) records the annotated interface declarations as protocol facts. Class names below are relative to `com.team` in JADX output.

## Origins and common parameters

School API: configured school HTTPS origin, initially `https://hselyceum.eljur.ru` in `common/ApiConstants`. School directory: `https://global.eljur.ru`. Configure school hostname and `vendor` independently for custom domains.

Every recovered Eljur request uses `devkey` and `vendor`; v3 uses `out_format=json`. Authenticated v3 and control-work calls carry `auth_token` as a query parameter. The app supplies `User-Agent: Dalvik/2.1.0 (Linux; U; Android 11; Pixel 4 Build/RP1A.200720.011)` on many, but not all, interfaces. The SDK uses it consistently. Several interfaces accept a `Cookie` header whose APK default is empty. No signing/HMAC algorithm was found in the recovered request definitions.

## Endpoint map

Common parameters above are omitted from the table.

| HTTP | Path | Additional query/body | Evidence class |
| --- | --- | --- | --- |
| POST | `/apiv3/auth` | JSON `login`, `password`; no auth_token | `feature_login/data/remote/LoginApi`, `LoginRequest` |
| GET | `/api/schools/mobileapp` | `value` | `feature_choose_school/data/remote/ChooseSchoolApi` |
| GET | `/apiv3/getrules` | None | `feature_profile/data/network/ProfileApi` |
| GET | `/apiv3/getperiods` | `weeks`, `show_disabled`: lowercase booleans | `feature_marks/data/remote/PeriodsApi` |
| GET | `/apiv3/getdiary` | `student`, `days`, `rings` (main diary uses integer `1`) | `feature_diary/data/remote/DiaryApi` |
| GET | `/apiv3/getmarks` | `student`, `days` | `feature_marks/data/remote/MarksApi` |
| GET | `/apiv3/getfinalassessments` | Optional `student` (year-results variant supplies it) | `feature_year_results/data/remote/YearResultsApi` |
| GET | `/apiv3/getmessages` | `folder`, `unreadonly`, `limit`, `page`, optional `filter` | `feature_messages/data/remote/MessagesApi` |
| GET | `/apiv3/getmessageinfo` | `id` | `feature_message_content/data/api/MessageContentApi` |
| GET | `/apiv3/getmessagereceivers` | None | `feature_send_message/data/remote/MessageApi` |
| POST | `/apiv3/sendmessage` | Query `id`; JSON `subject`, `text`, `users_to`, `fid`, `filename` | `feature_send_message/data/remote/MessageApi`, `SendMessageRequest` |
| GET | `/apiv3/getboardnotices` | `limit`, `page` | `feature_announcements/data/remote/AnnouncementsApi` |
| GET | `/apiv3/getboardnoticeinfo` | `id` | `feature_announcement_content/data/remote/AnnouncementInfoApi` |
| GET | `/journal-cw-ajax-action` | `method=cw.get_by_student_id`, `student_id`, `dateStart`, `dateEnd`, `lesson_id` | `feature_control_works/data/remote/ControlWorksApi` |
| POST | Dynamic URL from `getrules.result.uploadFileUrl` | Multipart field `userfile`; file bytes, filename, MIME type | `feature_send_message/presentation/SendMessageViewModel` fallback output |

The marks diary variant sends `person_id` instead of `student`; the homework variant sends boolean `rings=true` instead of `rings=1`. The SDK uses the main diary variant, which already includes homework and assessments. These are alternate app projections of the same route, not additional server endpoints.

Message defaults: `unreadonly=no`, `limit=20`, `page=1`. The SDK's `unread_only=True` maps to `yes`; this non-default value is an inference and requires live verification. `folder` values `inbox` and `sent` are used by the APK. `filter` is passed unchanged. Announcement defaults: `limit=20`, `page=1`. The SDK leaves pagination to callers.

`SendMessageViewModel` joins selected recipient user IDs with commas. It pairs `fid` and `filename` arrays from uploaded files. The query `id` comes from `PreferencesManager.getPersonId()` converted to an integer, falling back to zero in the app; it is not a reply-message ID. The SDK requires the caller to specify it. Upload success requires `success=true` and nonempty `file`/`name` strings.

## Response envelopes

API v3:

```json
{"response":{"state":200,"error":null,"result":{}}}
```

`feature_login/data/repository/LoginRepositoryImpl` accepts application `state=200` and reads `result.token` and `result.expires`. HTTP 200 alone does not establish success. `expires` is modeled as a string; its interpretation is unverified and the SDK preserves it without automatic refresh.

Non-v3 responses:

| Route | Top-level fields modeled by APK |
| --- | --- |
| School directory | `result` boolean, `options` array, `error` string |
| Control works | `rows` array, `datesState` object, `error`, `is_lms_control_works_available` |
| File upload | `state`, `success`, `file`, `url`, `name`, `error`, `error_code` |

Error mapping of state/HTTP 401 and 403 to `AuthenticationError` and 429 to `RateLimitError` is SDK policy. The precise production error-state vocabulary is not recovered. Other non-200 states raise `APIError`; malformed envelopes raise `ProtocolError`.

## Observed result shapes

These field paths come from model declarations, not captured live data. Fields can be null, omitted, or differ across schools. The client returns JSON to preserve differences.

| Result | Observed structure |
| --- | --- |
| Rules/profile | `id`, `name`, `firstname`, `lastname`, `roles`, `vendor`, `relations.students` map, `relations.groups` map, `uploadFileUrl`, school and support details |
| Related student | Map key is student ID; fields include `name`, `title`, `class`, `parallel`, `firstname`, `lastname`, `rules` |
| Periods | `students` array → `periods` array → `weeks` array, with `start`, `end`, `title` |
| Diary | `students` map → `days` map → `items` map and `items_extday` array |
| Lesson | `name`, `num`, `lesson_id`, `teacher`, `room`, `starttime`, `endtime`, `topic`, `homework`, `assessments`, `files`, `resources` |
| Homework | Main diary uses a map of entries with `id`, `individual`, `value`; extra-day homework is generic JSON |
| Diary file | `filename`, `link`, `toid`; another app projection uses `id`, `name`, `url` |
| Marks | `students` map → `lessons` array → `marks` array; lesson has `average`, `average_convert`, `lesson_id` |
| Mark | `value`, `date`, `weight`, `weight_float`, `count`, `countas`, `comment`, `lesson_comment`, `mtype` |
| Final assessments | `students` map → `items` array → `assessments` array; assessment has `period`, `value`, `convert`, `comment` |
| Messages | `count`, `total`, `messages` array; each includes `id`, `date`, `subject`, `short_text`, `unread`, `user_from`, `users_to` |
| Receivers | `groups` array → `users` / `subgroups` arrays; recipient ID is serialized as `name`, alongside `firstname`, `lastname`, `search`, `info` |
| Notices | `count`, `total`, `total_unread`, `notices` array |
| Notice detail | `notice` object including `text`, `files`, `user_from`, `date_actual_before` |

No grade-average computation is added: the server supplies averages and assessment weighting can vary by school.

## What remains unverified

Authenticated requests have not been run. Permissions and availability depend on account role and school. The control-work date format and web-cookie requirements require live verification. SSO/ESIA, token refresh/revocation, unread side effects, production rate limits, and other routes absent from this APK are not implemented or promised. Tests validate wire serialization and failure handling against synthetic fixtures, not server availability.
