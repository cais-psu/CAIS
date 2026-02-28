---
title: Team
layout: default
permalink: /team/
nav:
  order: 3
  tooltip: Members
---

# Principal Investigator (PI)
{% include list.html
   data="members"
   component="portrait"
   filter="role == 'pi' and !alumni"
%}

# PhD Students
{% include list.html
   data="members"
   component="portrait"
   filter="role =~ /^phd$/i and !alumni"
%}

# MS Students
{% include list.html
   data="members"
   component="portrait"
   filter="role =~ /^ms$/i and !alumni"
%}

# Visiting Students / Scholars
{% include list.html
   data="members"
   component="portrait"
   filter="role =~ /visitor/i and !alumni"
%}

# Undergraduates
{% include list.html
   data="members"
   component="portrait"
   filter="role =~ /undergrad/i and !alumni"
%}

# Alumni

## Master's Students
{% assign ms_alumni = site.members | where_exp: "m", "m.alumni and m.role == 'ms'" | sort: "end_date" | reverse %}
<ul>
{% for member in ms_alumni %}
<li>{{ member.name }}{% if member.dates %}, {{ member.dates }}{% endif %}</li>
{% endfor %}
</ul>

## Visiting Scholars
{% assign vs_alumni = site.members | where_exp: "m", "m.alumni and m.role == 'visitor'" | sort: "end_date" | reverse %}
<ul>
{% for member in vs_alumni %}
<li>{{ member.name }}{% if member.dates %}, {{ member.dates }}{% endif %}</li>
{% endfor %}
</ul>

## Undergraduates
{% assign ug_alumni = site.members | where_exp: "m", "m.alumni and m.role == 'undergrad'" | sort: "end_date" | reverse %}
<ul>
{% for member in ug_alumni %}
<li>{{ member.name }}{% if member.dates %}, {{ member.dates }}{% endif %}</li>
{% endfor %}
</ul>


