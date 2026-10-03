// Preview deployment of the Waterville City Code assistant (staff desk and public tools).
//
// A second container app and a manual refresh job in the EXISTING Container Apps
// environment. It reads the existing AI Search service and Azure OpenAI account
// through role assignments for its own identities, writes only its own index
// (waterville-code-preview) and its own storage account, and never changes a
// production resource. Every shared resource below is declared `existing`.
//
// The refresh job's write right on the search service is scoped to the preview
// index alone: infra/deploy-preview.sh creates the index definition (as the
// deploying principal) and assigns Search Index Data Contributor at
// .../searchServices/{name}/indexes/waterville-code-preview, since Bicep cannot
// target an index scope. This template grants the job no service-wide search
// role, so it cannot touch the production index.
//
// Deploy with infra/deploy-preview.sh, never by hand against main.bicep.

targetScope = 'resourceGroup'

@description('Region for the new resources. Must be the Container Apps environment region.')
param location string = resourceGroup().location

@description('Full image reference, e.g. watervilleacrxxxx.azurecr.io/waterville:preview-abc1234.')
param image string

// ------------------------------------------------------------------ existing resource names

@description('Existing Container Apps environment.')
param envName string = 'waterville-env'

@description('Existing container registry.')
param acrName string

@description('Existing AI Search service.')
param searchName string

@description('Existing Azure OpenAI account.')
param openAiName string

@description('Existing Log Analytics workspace (the environment already logs to it).')
param logsName string

@description('Chat deployment on the OpenAI account.')
param chatDeployment string = 'chat'

@description('Embedding deployment on the OpenAI account, used by the refresh job.')
param embeddingDeployment string = 'embedding'

param embeddingModel string = 'text-embedding-3-large'
param embeddingDimensions int = 3072

@description('Set for reasoning models (gpt-5*, o*): low, medium or high. Empty for others.')
param chatReasoningEffort string = ''

// ------------------------------------------------------------------ preview settings

@description('Name prefix for the preview resources.')
param name string = 'waterville-preview'

@description('Search index the preview reads and its refresh job writes. Never the production index.')
param searchIndex string = 'waterville-code-preview'

@description('0 scales to zero when idle (about 20 seconds of cold start).')
@minValue(0)
@maxValue(1)
param minReplicas int = 0

@description('In-memory rate limits and login throttling are per replica, so the preview runs one.')
@minValue(1)
@maxValue(1)
param maxReplicas int = 1

@description('STAFF_USERS value: JSON {"username": "scrypt$..."} from `python -m app.auth hash NAME`.')
@secure()
param staffUsers string

@description('SESSION_SECRET value: HMAC key for staff session cookies (`python -m app.auth secret`).')
@secure()
param sessionSecret string

@description('Log public questions (PII-scrubbed) to the store for the insights page.')
param questionLog bool = true

@description('Days a logged public question is kept before the app deletes it. 0 keeps them.')
@minValue(0)
param questionLogRetentionDays int = 365

@description('Keep storage write and delete audit logs in the existing workspace.')
param storageAuditLogs bool = true

// Guard rails: the preview must never take a production name or index.
var productionNames = [ 'waterville-app', 'waterville-refresh' ]
var safeName = contains(productionNames, name) || contains(productionNames, '${name}-refresh') ? 'invalid-name-${name}' : name
var safeIndex = searchIndex == 'waterville-code' ? 'invalid-index-waterville-code' : searchIndex

var suffix = uniqueString(resourceGroup().id)
var tags = { app: 'waterville-code-assistant', environment: 'preview' }

// Built-in role definition IDs.
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  storageTableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
}

@description('Custom hostname bound to the preview app (empty for none). Keeps the binding on redeploys.')
param customDomain string = 'waterville-preview.nehemia.dev'

@description('Name of the Azure-managed certificate for customDomain in the environment.')
param customDomainCertificate string = 'mc-waterville-env-waterville-previ-1801'

// ------------------------------------------------------------------ existing (read only)

resource env 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: envName
}

resource domainCert 'Microsoft.App/managedEnvironments/managedCertificates@2024-03-01' existing = if (!empty(customDomain)) {
  parent: env
  name: customDomainCertificate
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource search 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchName
}

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiName
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logsName
}

// ------------------------------------------------------------------ identities (new)

// The app reads the index and the model, and reads and writes its own tables.
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${safeName}-id'
  location: location
  tags: tags
}

// The refresh job writes the preview index. A separate identity keeps index
// write rights away from the internet-facing app.
resource jobIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${safeName}-refresh-id'
  location: location
  tags: tags
}

// ------------------------------------------------------------------ storage (new)

// Cases, drafts, answers, question log and change alerts. Microsoft Entra only:
// shared keys are disabled, so the account cannot be reached with a key.
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take('wvpreview${suffix}', 24)
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        table: { enabled: true, keyType: 'Account' }
        blob: { enabled: true, keyType: 'Account' }
      }
    }
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

// The app's Store creates missing tables too; creating them here means the
// identities never need to. `changes` is declared on its own: the refresh
// job's table role is scoped to it alone.
var tableNames = [ 'cases', 'caseitems', 'drafts', 'questions', 'feedback', 'answers' ]

resource tables 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = [for t in tableNames: {
  parent: tableService
  name: t
}]

resource changesTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'changes'
}

resource storageAudit 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (storageAuditLogs) {
  scope: tableService
  name: 'preview-table-audit'
  properties: {
    workspaceId: logs.id
    logs: [
      { category: 'StorageWrite', enabled: true }
      { category: 'StorageDelete', enabled: true }
    ]
  }
}

// ------------------------------------------------------------------ role assignments (new)

resource appAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, appIdentity.id, roles.acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, jobIdentity.id, roles.acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource appSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, appIdentity.id, roles.searchIndexDataReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// The job's search role (Search Index Data Contributor on the preview index
// only) is assigned by infra/deploy-preview.sh after it creates the index:
// role assignments at an index scope cannot be declared in Bicep. The job runs
// with SEARCH_INDEX_UPDATE=never, so it never needs to manage the index
// definition and holds no service-wide search role.

resource appOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, appIdentity.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jobOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, jobIdentity.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource appTables 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, appIdentity.id, roles.storageTableDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageTableDataContributor)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// The job writes change alerts only, so its table role covers the `changes`
// table and nothing else (cases, drafts, answers and the question log stay
// out of its reach).
resource jobTables 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: changesTable
  name: guid(changesTable.id, jobIdentity.id, roles.storageTableDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageTableDataContributor)
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ------------------------------------------------------------------ container app and job (new)

var tableEndpoint = storage.properties.primaryEndpoints.table

var commonEnv = [
  { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
  { name: 'AZURE_SEARCH_INDEX', value: safeIndex }
  { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
  { name: 'STORAGE_TABLE_ENDPOINT', value: tableEndpoint }
]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: safeName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        customDomains: empty(customDomain) ? [] : [
          { name: customDomain, certificateId: domainCert.id, bindingType: 'SniEnabled' }
        ]
      }
      registries: [ { server: acr.properties.loginServer, identity: appIdentity.id } ]
      secrets: [
        { name: 'staff-users', value: staffUsers }
        { name: 'session-secret', value: sessionSecret }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(commonEnv, [
            { name: 'APP_ENV', value: 'preview' }
            { name: 'AZURE_CLIENT_ID', value: appIdentity.properties.clientId }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeployment }
            { name: 'CHAT_REASONING_EFFORT', value: chatReasoningEffort }
            { name: 'QUESTION_LOG', value: questionLog ? '1' : '0' }
            { name: 'QUESTION_LOG_RETENTION_DAYS', value: string(questionLogRetentionDays) }
            { name: 'STAFF_USERS', secretRef: 'staff-users' }
            { name: 'SESSION_SECRET', secretRef: 'session-secret' }
          ])
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '30' } } } ]
      }
    }
  }
  dependsOn: [ appAcrPull, appSearchReader, appOpenAi, appTables, tables, changesTable ]
}

resource refreshJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${safeName}-refresh'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${jobIdentity.id}': {} }
  }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Manual'
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      replicaTimeout: 7200
      replicaRetryLimit: 0
      registries: [ { server: acr.properties.loginServer, identity: jobIdentity.id } ]
    }
    template: {
      containers: [
        {
          name: 'refresh'
          image: image
          command: [ '/usr/local/bin/refresh' ]
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: concat(commonEnv, [
            { name: 'APP_ENV', value: 'preview' }
            { name: 'AZURE_CLIENT_ID', value: jobIdentity.properties.clientId }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment }
            { name: 'AZURE_OPENAI_EMBEDDING_MODEL', value: embeddingModel }
            { name: 'EMBEDDING_DIMENSIONS', value: string(embeddingDimensions) }
            // The index definition is managed by deploy-preview.sh; the job only writes documents.
            { name: 'SEARCH_INDEX_UPDATE', value: 'never' }
          ])
        }
      ]
    }
  }
  dependsOn: [ jobAcrPull, jobOpenAi, jobTables, tables, changesTable ]
}

output appName string = app.name
output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output jobName string = refreshJob.name
output searchIndex string = safeIndex
output storageAccount string = storage.name
output tableEndpoint string = tableEndpoint
output appIdentityName string = appIdentity.name
output jobIdentityName string = jobIdentity.name
output jobPrincipalId string = jobIdentity.properties.principalId
output searchId string = search.id
