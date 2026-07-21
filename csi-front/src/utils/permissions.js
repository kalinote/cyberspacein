export const PERM = Object.freeze({
  pages: {
    overview: { visible: 'page:overview:visible', access: 'page:overview:access' },
    search: { visible: 'page:search:visible', access: 'page:search:access' },
    action: {
      visible: 'page:action:visible',
      access: 'page:action:access',
      create: { visible: 'page:action:create:visible', access: 'page:action:create:access' },
      history: { visible: 'page:action:history:visible', access: 'page:action:history:access' },
      blueprints: { visible: 'page:action:blueprints:visible', access: 'page:action:blueprints:access' },
      detail: { visible: 'page:action:detail:visible', access: 'page:action:detail:access' },
      tasks: { visible: 'page:action:tasks:visible', access: 'page:action:tasks:access' },
      resource: {
        visible: 'page:action:resource:visible',
        access: 'page:action:resource:access',
        nodes: { visible: 'page:action:resource:nodes:visible', access: 'page:action:resource:nodes:access' },
        components: { visible: 'page:action:resource:components:visible', access: 'page:action:resource:components:access' },
        handles: { visible: 'page:action:resource:handles:visible', access: 'page:action:resource:handles:access' },
        proxy: { visible: 'page:action:resource:proxy:visible', access: 'page:action:resource:proxy:access' },
        accounts: { visible: 'page:action:resource:accounts:visible', access: 'page:action:resource:accounts:access' },
        corpus: { visible: 'page:action:resource:corpus:visible', access: 'page:action:resource:corpus:access' }
      }
    },
    target: {
      visible: 'page:target:visible',
      access: 'page:target:access',
      highlights: { visible: 'page:target:highlights:visible', access: 'page:target:highlights:access' },
      wiki: { visible: 'page:target:wiki:visible', access: 'page:target:wiki:access' }
    },
    agent: {
      visible: 'page:agent:visible',
      access: 'page:agent:access',
      sessions: { visible: 'page:agent:sessions:visible', access: 'page:agent:sessions:access' },
      config: {
        visible: 'page:agent:config:visible',
        access: 'page:agent:config:access',
        workspaces: { visible: 'page:agent:config:workspaces:visible', access: 'page:agent:config:workspaces:access' },
        agents: { visible: 'page:agent:config:agents:visible', access: 'page:agent:config:agents:access' },
        models: { visible: 'page:agent:config:models:visible', access: 'page:agent:config:models:access' },
        prompts: { visible: 'page:agent:config:prompts:visible', access: 'page:agent:config:prompts:access' },
        systemPrompts: { visible: 'page:agent:config:system-prompts:visible', access: 'page:agent:config:system-prompts:access' },
        skills: { visible: 'page:agent:config:skills:visible', access: 'page:agent:config:skills:access' },
        tools: { visible: 'page:agent:config:tools:visible', access: 'page:agent:config:tools:access' },
        sandboxes: { visible: 'page:agent:config:sandboxes:visible', access: 'page:agent:config:sandboxes:access' }
      },
      analysis: { visible: 'page:agent:analysis:visible', access: 'page:agent:analysis:access' }
    },
    system: {
      visible: 'page:system:visible',
      access: 'page:system:access',
      config: { visible: 'page:system:config:visible', access: 'page:system:config:access' },
      alert: { visible: 'page:system:alert:visible', access: 'page:system:alert:access' },
      permissions: {
        visible: 'page:system:permissions:visible',
        access: 'page:system:permissions:access',
        tabs: {
          users: {
            visible: 'page:system:permissions:users:visible',
            access: 'page:system:permissions:users:access'
          },
          groups: {
            visible: 'page:system:permissions:groups:visible',
            access: 'page:system:permissions:groups:access'
          },
          dictionary: {
            visible: 'page:system:permissions:dictionary:visible',
            access: 'page:system:permissions:dictionary:access'
          }
        }
      }
    }
  },
  operations: {
    search: {
      entity: { execute: 'operation:search:entity:execute' },
      template: {
        read: 'operation:search:template:read',
        create: 'operation:search:template:create',
        update: 'operation:search:template:update',
        delete: 'operation:search:template:delete'
      }
    },
    content: {
      article: { read: 'operation:content:article:read' },
      forum: { read: 'operation:content:forum:read' },
      platform: { read: 'operation:content:platform:read', create: 'operation:content:platform:create' }
    },
    target: {
      highlight: { update: 'operation:target:highlight:update' },
      wiki: {
        read: 'operation:target:wiki:read',
        create: 'operation:target:wiki:create',
        update: 'operation:target:wiki:update',
        delete: 'operation:target:wiki:delete',
        execute: 'operation:target:wiki:execute'
      }
    },
    action: {
      instance: { read: 'operation:action:instance:read', execute: 'operation:action:instance:execute' },
      blueprint: { read: 'operation:action:blueprint:read', create: 'operation:action:blueprint:create' },
      node: {
        read: 'operation:action:node:read',
        create: 'operation:action:node:create',
        update: 'operation:action:node:update',
        delete: 'operation:action:node:delete'
      },
      config: { read: 'operation:action:config:read', create: 'operation:action:config:create' },
      schedule: {
        read: 'operation:action:schedule:read',
        create: 'operation:action:schedule:create',
        update: 'operation:action:schedule:update',
        delete: 'operation:action:schedule:delete'
      },
      account: {
        listRead: 'operation:action:account-list:read',
        detailRead: 'operation:action:account-detail:read',
        secretRead: 'operation:action:account-secret:read',
        create: 'operation:action:account:create',
        update: 'operation:action:account:update',
        delete: 'operation:action:account:delete'
      }
    },
    agent: {
      agent: {
        read: 'operation:agent:agent:read',
        create: 'operation:agent:agent:create',
        update: 'operation:agent:agent:update',
        delete: 'operation:agent:agent:delete',
        execute: 'operation:agent:agent:execute'
      },
      session: { read: 'operation:agent:session:read' },
      modelConfig: {
        listRead: 'operation:agent:model-config-list:read',
        detailRead: 'operation:agent:model-config-detail:read',
        secretRead: 'operation:agent:model-secret:read',
        create: 'operation:agent:model-config:create',
        update: 'operation:agent:model-config:update',
        delete: 'operation:agent:model-config:delete'
      },
      promptTemplate: {
        read: 'operation:agent:prompt-template:read',
        create: 'operation:agent:prompt-template:create',
        update: 'operation:agent:prompt-template:update',
        delete: 'operation:agent:prompt-template:delete'
      },
      systemPrompt: {
        read: 'operation:agent:system-prompt:read',
        create: 'operation:agent:system-prompt:create',
        update: 'operation:agent:system-prompt:update',
        delete: 'operation:agent:system-prompt:delete'
      },
      skill: {
        read: 'operation:agent:skill:read',
        create: 'operation:agent:skill:create',
        update: 'operation:agent:skill:update',
        delete: 'operation:agent:skill:delete'
      },
      workspace: {
        read: 'operation:agent:workspace:read',
        create: 'operation:agent:workspace:create',
        update: 'operation:agent:workspace:update',
        delete: 'operation:agent:workspace:delete'
      },
      sandbox: {
        read: 'operation:agent:sandbox:read',
        create: 'operation:agent:sandbox:create',
        delete: 'operation:agent:sandbox:delete'
      },
      tool: { read: 'operation:agent:tool:read' }
    },
    system: {
      users: {
        listRead: 'operation:system:user-list:read',
        detailRead: 'operation:system:user-detail:read',
        create: 'operation:system:user:create',
        profileUpdate: 'operation:system:user-profile:update',
        groupUpdate: 'operation:system:user-group:update',
        passwordExecute: 'operation:system:user-password:execute',
        statusExecute: 'operation:system:user-status:execute',
        expiryUpdate: 'operation:system:user-expiry:update',
        delete: 'operation:system:user:delete',
        assignmentScopeUpdate: 'operation:system:assignment-scope:update'
      },
      groups: {
        read: 'operation:system:group:read',
        create: 'operation:system:group:create',
        update: 'operation:system:group:update',
        delete: 'operation:system:group:delete'
      },
      permissionCodes: {
        read: 'operation:system:permission-code:read',
        create: 'operation:system:permission-code:create',
        update: 'operation:system:permission-code:update',
        delete: 'operation:system:permission-code:delete',
        execute: 'operation:system:permission-code:execute'
      },
      sessions: {
        read: 'operation:system:login-session:read',
        execute: 'operation:system:login-session:execute'
      },
      config: {
        read: 'operation:system:config:read',
        update: 'operation:system:config:update',
        execute: 'operation:system:config:execute'
      }
    }
  }
})
