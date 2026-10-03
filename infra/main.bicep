// Waterville City Code assistant: Azure AI Search + Azure OpenAI + Container Apps.
// Everything authenticates with managed identities; Azure OpenAI has key auth disabled.

targetScope = 'resourceGroup'

@description('Azure region. Must have quota for both models.')
param location string = resourceGroup().location

@description('Region for AI Search. Defaults to location; set another when that region lacks Search capacity.')
param searchLocation string = location

@description('Short prefix for resource names.')
param prefix string = 'waterville'

@description('Chat model name, e.g. gpt-5-mini or gpt-4.1-mini.')
param chatModel string

@description('Chat model version, as listed by `az cognitiveservices model list`.')
param chatModelVersion string

@description('Deployment SKU for the chat model.')
param chatSku string = 'GlobalStandard'

@description('Chat capacity in thousands of tokens per minute. This is the hard ceiling on spend.')
param chatCapacity int = 50

@description('Set for reasoning models (gpt-5*, o*): low, medium or high. Empty for others.')
param chatReasoningEffort string = ''

param embeddingModel string = 'text-embedding-3-large'
param embeddingModelVersion string = '1'
param embeddingSku string = 'GlobalStandard'
param embeddingCapacity int = 150
param embeddingDimensions int = 3072

@description('Deploy the container app and job. False on the first pass, before the image exists.')
param deployApps bool = false

@description('Full image reference, e.g. myacr.azurecr.io/waterville:abc123.')
param image string = ''

@description('Minimum app replicas. 1 keeps the app warm; 0 scales to zero when idle (about 20 seconds of cold start).')
param minReplicas int = 1

@description('Cron schedule (UTC) for the refresh job. Default: Mondays 07:00.')
param refreshCron string = '0 7 * * 1'

param searchIndex string = 'waterville-code'

@description('Custom hostname bound to the app (empty for none). Keeps the binding on redeploys.')
param customDomain string = 'waterville.nehemia.dev'

@description('Name of the Azure-managed certificate for customDomain in the environment.')
param customDomainCertificate string = 'mc-waterville-env-waterville-nehem-9228'

var suffix = uniqueString(resourceGroup().id)
var tags = { app: 'waterville-code-assistant' }

// Built-in role definition IDs.
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

// ------------------------------------------------------------------ identities

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-app-id'
  location: location
  tags: tags
}

resource jobIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-refresh-id'
  location: location
  tags: tags
}

// ------------------------------------------------------------------ monitoring

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ------------------------------------------------------------------ registry

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${prefix}acr${suffix}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// ------------------------------------------------------------------ AI Search

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${prefix}-search-${suffix}'
  location: searchLocation
  tags: tags
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    semanticSearch: 'standard'
    disableLocalAuth: false
    authOptions: {
      aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' }
    }
  }
}

// ------------------------------------------------------------------ Azure OpenAI

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${prefix}-openai-${suffix}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${prefix}-openai-${suffix}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: 'embedding'
  sku: { name: embeddingSku, capacity: embeddingCapacity }
  properties: {
    model: { format: 'OpenAI', name: embeddingModel, version: embeddingModelVersion }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: 'chat'
  sku: { name: chatSku, capacity: chatCapacity }
  properties: {
    model: { format: 'OpenAI', name: chatModel, version: chatModelVersion }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [ embeddingDeployment ] // deployments on one account must not run in parallel
}

// ------------------------------------------------------------------ role assignments

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

resource jobSearchData 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, jobIdentity.id, roles.searchIndexDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource jobSearchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, jobIdentity.id, roles.searchServiceContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

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

// The search service vectorizes queries itself, so it calls Azure OpenAI too.
resource searchOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, search.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ------------------------------------------------------------------ Container Apps

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource domainCert 'Microsoft.App/managedEnvironments/managedCertificates@2024-03-01' existing = if (!empty(customDomain)) {
  parent: env
  name: customDomainCertificate
}

var commonEnv = [
  { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
  { name: 'AZURE_SEARCH_INDEX', value: searchIndex }
  { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
]

resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: '${prefix}-app'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
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
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(commonEnv, [
            { name: 'AZURE_CLIENT_ID', value: appIdentity.properties.clientId }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeployment.name }
            { name: 'CHAT_REASONING_EFFORT', value: chatReasoningEffort }
          ])
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        // In-memory rate limits are per replica; keep the count small.
        maxReplicas: 2
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '30' } } } ]
      }
    }
  }
  dependsOn: [ appAcrPull, appSearchReader, appOpenAi ]
}

resource refreshJob 'Microsoft.App/jobs@2024-03-01' = if (deployApps) {
  name: '${prefix}-refresh'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${jobIdentity.id}': {} }
  }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: { cronExpression: refreshCron, parallelism: 1, replicaCompletionCount: 1 }
      replicaTimeout: 7200
      replicaRetryLimit: 1
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
            { name: 'AZURE_CLIENT_ID', value: jobIdentity.properties.clientId }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment.name }
            { name: 'AZURE_OPENAI_EMBEDDING_MODEL', value: embeddingModel }
            { name: 'EMBEDDING_DIMENSIONS', value: string(embeddingDimensions) }
          ])
        }
      ]
    }
  }
  dependsOn: [ jobAcrPull, jobSearchData, jobSearchService, jobOpenAi, searchOpenAi, chatDeployment ]
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output openAiEndpoint string = openai.properties.endpoint
output appName string = deployApps ? app.name : ''
output appUrl string = deployApps ? 'https://${app!.properties.configuration.ingress.fqdn}' : ''
output jobName string = deployApps ? refreshJob.name : ''
