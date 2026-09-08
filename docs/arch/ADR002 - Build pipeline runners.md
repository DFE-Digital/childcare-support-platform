<!-- 
    Choose an identifier for the ADR by adding 1 to the previous ADR's id. 

    Also choose a title, which should be a very short description of the 
    decision itself. Make it specific.    
-->

# <!-- Identifier: --> ADR002 - <!-- Title: --> Build Pipeline Runners

<!-- Metadata section. All fields are mandatory. -->
- **Status**: Draft
- **Date**: <!-- The day the draft was started, in the YYYY-MM-DD format, for example '1970-01-01' --> 2026-08-19
- **Author**:<!-- Your full name as the owner of the decision, for example 'Joe Bloggs'. --> Isaac Naylor

## Decision

<!-- 
    In a few sentences, describe the decision taken. 
-->

The decision has been made to go with Option 2 (Self-hosted runners).

The reason for this decision, is that we do not have a timeline on when we would have Github hosted runners made available to us, and using self-hosted runners will prevent us from getting blocked by another team for this piece of work.

## Context

<!-- 
    Describe the forces and circumstances that brought about this decision. 
-->

When running the build pipeline for the application, it has a dependency on data that is hosted within Azure.
Because of security restrictions on the azure environment, it should not typically be viable for an actions runner hosted in Github to access the data on our private network.
This means that we need to ensure the actions runner is able to access the data in a secure way, and there are 2 considered options for how to do that.

## Options considered

<!-- 
    Briefly describe each option considered as a numbered list. Start with the selected option.
    It's usually wise to include a 'do nothing' option.

    e.g.

    1. (SELECTED) PostgreSQL
    2. Oracle
    3. SQL Server  
-->

1. (SELECTED - Tactical) Self-hosted runners, on a virtual machine within our Azure estate.
2. (Preferred) Github hosted runners, injected into the Azure Private Network.

## Consequences

<!-- 
    For each of the options above, describe positive and negative consequences
    of selecting that option. Create a new section for each option under a heading.

    Remember a law of architecture: There are no solutions, only trade-offs. Make
    sure to include any negative consequences of the selected option.

    e.g.

    ### Option 1 - XXX

    - Consequence 1
    - Consequence 2

    ### Option 2 - XXX

    etc.
-->

### Option 1 - Github hosted runners

Positives:

- Github hosted runners require little to no maintenance

Negatives:

- This requires collaboration with the wider DfE Digital Tools / Infrastructure teams, to co-ordinate the configuration 

### Option 2 - Self-hosted runners

Positives:

- Manageable within the team, no external dependencies

Negatives:

- Requires more set-up / overall maintenance time

## Advice

<!--
    List of advice gathered to make this decision, including the names and role of 
    advisors and the date each piece of advice was gathered.

    Before submitting a decision, you are expected to gather advice from all team 
    members or stakeholders who will be affected by the decision.
-->

John Carter suggested that the Github Hosted Runners (Option 1) would be the sensible option to go with, and this is our preferred implementation.
However, he also advised that the lead-time on getting Github Hosted Runners would be quite long, as it is a decision that must be made by the DfE Enterprise Team.

Pradeep Neelakandan has advised the team to go with Self-Hosted (Option 2), at least until a formal decision is made by the enterprise team.