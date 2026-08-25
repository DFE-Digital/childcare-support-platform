<!-- 
    Choose an identifier for the ADR by adding 1 to the previous ADR's id. 

    Also choose a title, which should be a very short description of the 
    decision itself. Make it specific.    
-->

# <!-- Identifier: --> ADR001 - <!-- Title: --> Azure API Boundary and APIM Approach

<!-- Metadata section. All fields are mandatory. -->
- **Status**: Draft - decision pending architectural review
- **Date**: <!-- The day the draft was started, in the YYYY-MM-DD format, for example '1970-01-01' --> 2026/08/25
- **Author**:<!-- Your full name as the owner of the decision, for example 'Joe Bloggs'. --> Robin Appleton-Power

## Decision
Decision Pending. 
This ADR records the investigation and options for determining the appropriate Azure API boundary and API-management approach. It does not assume a) that APIM is required simply because the existing solution uses AWS API Gateway b) that APIM is simply not needed without addressing the capability provided by the existing API boundary.
The decision will follow a review with senior DfE architects. The selected option must preserve required behaviour and security characteristics while remaining appropriate for the like-for-like migration, latency-sensitive request path, cost constraints and end-of-September deadline.
<!-- 
    In a few sentences, describe the decision taken. 
-->

## Context
The project is migrating an existing AWS solution to Azure. The chosen migration option is a like-for-like migration rather than a redesign. The migration is targeting the end of September 2026, while the project is still progressing through environment build. Given deadlines any departure from the existing architecture needs to be assessed for additional design, engineering, configuration/coding, testing, assurance and schedule risk.

The existing AWS request path is CloudFront → API Gateway → Lambda. Investigation of the AWS Terraform established that API Gateway is a REST API with a catch-all proxy method, requires an API key, associates the key with a usage plan and integrates with Lambda using an AWS proxy integration. The CloudFront Function adds the x-api-key header to /api/* requests before forwarding them to API Gateway. The browser therefore does not directly possess the API key.

The No. 10 team has confirmed the following key architectural findings: the API Gateway is primarily present to facilitate calling the Lambda from the CloudFront deployment; the API key is baked into the CloudFront deployment from AWS SSM Parameter Store at deployment time; a WAF is associated with the API Gateway and has default protections enabled; and no throttling or rate limiting is enabled, although rate-limiting capability exists.

The API Gateway configuration identified in Terraform uses authorization = NONE. No OAuth, Cognito or per-user API credentials have been identified. The API key therefore should not be interpreted as consumer authentication. Its role in the existing implementation is better understood as part of the trusted CloudFront-to-API-Gateway request path and API boundary.

Origin protection is an important architectural consideration. The intended request path is through the public edge and then the API boundary to the backend. The Azure design must establish how the Function is prevented from being directly invoked in a way that bypasses the intended Front Door/WAF path. The same broader principle applies to other origins, such as Blob Storage: the design should consider whether an origin can be accessed directly rather than through the intended edge.

The API is internet-facing in the sense that browser clients need to reach it through the public edge, but it is not an open public API in the sense of exposing an unauthenticated backend endpoint to clients. This distinction is relevant when assessing the need for an API-management service.

The API request path is latency-sensitive. Introducing additional network hops or processing layers therefore needs to be considered against the performance requirement rather than assuming that an additional service is neutral.

The No.10 team is providing read-only access to the AWS Production web console so that the deployed API Gateway, WAF and associated settings can be inspected directly. This is intended to verify any remaining details that cannot be confidently established from Terraform alone.

The architectural question is not simply 'What is the Azure equivalent of API Gateway?'. The question is: what capabilities and security boundaries must be preserved, what Azure options can provide them, and which option represents the appropriate balance of like-for-like behaviour, security, latency, delivery effort, cost, enterprise standards and schedule risk?
<!-- 
    Describe the forces and circumstances that brought about this decision. 
-->

## Options considered
1. Azure Front Door -> APIM-->Function.
Use Azure API management as the API boundary behind Front Door. This is the closest Azure service like-for-like substitution for the existing CloudFront -> API Gateway -> Lambda path.

2. Front Door --> Function
Do without a dedicated API management layer and use an approved Azure-native mechanism to preserve the required API behaviour and protect the function from direct invocation.

3. Alternate DfE-approved API approach
Adopt another DfE/Azure API pattern if other DfE architects identify an established enterprise approach that better meets the requirements and migration constraints.
<!-- 
    Briefly describe each option considered as a numbered list. Start with the selected option.
    It's usually wise to include a 'do nothing' option.

    e.g.

    1. (SELECTED) PostgreSQL
    2. Oracle
    3. SQL Server  
-->

## Consequences
Option 1 – Front Door → APIM → Function

Potential benefits:
• Provides a dedicated API boundary and is conceptually close to the existing AWS request path.
• May reduce the architectural change required to reproduce the existing API boundary and its protection model.
• Provides a platform for API policies and other API-management capabilities if those capabilities are genuinely required.
• May provide an established mechanism for controlling the gateway-to-backend relationship and reducing the need for a bespoke origin-protection design.

Potential consequences / risks:
• Introduces the ongoing Azure cost of APIM, which has already been raised as a concern.
• The existence of API Gateway in AWS is not, by itself, sufficient justification for APIM; the required capabilities must be demonstrated.
• APIM configuration, integration and assurance introduce engineering effort.
• If APIM provides capabilities not actually required by the migrated solution, the option may introduce unnecessary cost and complexity.

Option 2 – Front Door → Function
Potential benefits:
• Avoids the ongoing cost of a dedicated APIM layer.
• Reduces the number of services and potentially the number of hops in the request path.
• May be appropriate if the required API boundary and origin-protection capabilities can be provided using an approved Azure/DfE pattern.

Potential consequences / risks:
• Requires an explicit, secure and approved mechanism to prevent direct Function invocation and bypass of Front Door/WAF.
• Could depart further from the existing AWS architecture and therefore introduce additional design effort.
• May require additional infrastructure/configuration work and security, functional and performance testing.
• Any new origin-protection mechanism must be demonstrated to provide the required security boundary rather than simply assuming that Front Door/WAF is sufficient.
• The additional design and assurance effort could affect the end-of-September deadline and project estimates.

Option 3 – Alternative DfE-approved API pattern
Potential benefits:
• May align more closely with an established DfE enterprise architecture or platform pattern.
• Could provide an appropriate balance between security, cost, operational support, latency and delivery effort.
• Specialist input may identify an existing capability that avoids unnecessary bespoke design.
Potential consequences / risks:
• The specific alternative is currently undefined and requires specialist architectural advice.
• A materially different pattern may introduce additional design, engineering or assurance work.
• The option must be assessed carefully against the like-for-like objective and end-of-September deadline.
• The pattern must protect the required backend origins and preserve the API bahaviour

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

## Advice

<!--
    List of advice gathered to make this decision, including the names and role of 
    advisors and the date each piece of advice was gathered.

    Before submitting a decision, you are expected to gather advice from all team 
    members or stakeholders who will be affected by the decision.
-->
