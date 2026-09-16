
  ![on-push](../../actions/workflows/on-push.yaml/badge.svg)
  ![on-pull-request](../../actions/workflows/on-pull-request.yaml/badge.svg)
  ![on-schedule](../../actions/workflows/on-schedule.yaml/badge.svg)

  # cais-psu's Website

  Visit **[www.caislab.com](http://www.caislab.com)** 🚀

  _Built with [Lab Website Template](https://greene-lab.gitbook.io/lab-website-template-docs)_

## News tags

Use the following lowercase tags in news front matter. Choose one tag for the
main news event; add a second only when the post reports a separate achievement
(for example, a conference presentation and a student paper prize).

| Tag | Use for |
| --- | --- |
| `publications` | Paper acceptances and newly published research, including conference papers. |
| `conferences` | Presentations, attendance, and organizing at academic conferences, workshops, and research symposia. |
| `people` | New members and visitors, graduations, qualifying/comprehensive exams, defenses, and professional appointments. |
| `awards` | Prizes, scholarships, honors, and award nominations. |
| `funding` | Research grants and sponsored projects, including NSF CAREER and seed grants. |
| `outreach` | Invited university seminars, research visits, industry/public exhibitions, community showcases, and media coverage. |
| `lab-life` | Social activities, celebrations, and lab-wide milestones such as the lab launch. |

Example:

```yaml
tags:
  - conferences
  - awards
```

Classify the event described in the post rather than copying tags from a similar
post. A paper acceptance uses `publications`; the later conference presentation
uses `conferences`. A grant belongs in `funding`, and a news feature belongs in
`outreach`. An award deserves a second tag only if it is a distinct new result,
not an older achievement mentioned in passing. Add `awards` to an NSF CAREER
announcement because it reports both an honor and research funding.

Keep research topics (AI, robotics, manufacturing) in the title/body for keyword
search instead of adding them as news tags. Do not reintroduce `journals`,
`welcome`, `exams`, `milestones`, `activities`, or `grants`; their meanings are
covered above. Tags link back to the filtered News page from both excerpts and
individual posts.
