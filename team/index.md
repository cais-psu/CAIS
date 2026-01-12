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
{% include list.html
   data="members"
   component="portrait"
   filter="alumni"
   style="tiny"
%}
