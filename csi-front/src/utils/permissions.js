export const PERM = {
  pages: {
    search: {
      view: 'page:search:view',
      use: 'page:search:use'
    },
    action: {
      view: 'page:action:view',
      use: 'page:action:use',
      task: {
        view: 'page:action:task:view',
        use: 'page:action:task:use'
      }
    },
    target: {
      view: 'page:target:view',
      use: 'page:target:use'
    },
    agent: {
      view: 'page:agent:view',
      use: 'page:agent:use'
    },
    system: {
      view: 'page:system:view',
      alert: {
        view: 'page:system:alert:view',
        use: 'page:system:alert:use'
      },
      permissions: {
        view: 'page:system:permissions:view',
        use: 'page:system:permissions:use',
        tabs: {
          users: {
            view: 'page:system:permissions:userManagement:view',
            use: 'page:system:permissions:userManagement:use'
          },
          groups: {
            view: 'page:system:permissions:groupManagement:view',
            use: 'page:system:permissions:groupManagement:use'
          },
          dictionary: {
            view: 'page:system:permissions:dictManagement:view',
            use: 'page:system:permissions:dictManagement:use'
          }
        }
      }
    }
  },
  operations: {
    system: {
      permissions: {
        users: {
          listView: 'operation:system:permissions:userManagement:users:view',
          addView: 'operation:system:permissions:userManagement:users:add:view',
          addUse: 'operation:system:permissions:userManagement:users:add:use',
          detailView: 'operation:system:permissions:userManagement:users:detail:view',
          detailUse: 'operation:system:permissions:userManagement:users:detail:use',
          editView: 'operation:system:permissions:userManagement:users:edit:view',
          editUse: 'operation:system:permissions:userManagement:users:edit:use'
        },
        groups: {
          listView: 'operation:system:permissions:groupManagement:groups:view',
          addView: 'operation:system:permissions:groupManagement:groups:add:view',
          addUse: 'operation:system:permissions:groupManagement:groups:add:use',
          detailView: 'operation:system:permissions:groupManagement:groups:detail:view',
          detailUse: 'operation:system:permissions:groupManagement:groups:detail:use',
          editView: 'operation:system:permissions:groupManagement:groups:edit:view',
          editUse: 'operation:system:permissions:groupManagement:groups:edit:use'
        },
        dict: {
          listView: 'operation:system:permissions:dictManagement:dict:view',
          addView: 'operation:system:permissions:dictManagement:dict:add:view',
          addUse: 'operation:system:permissions:dictManagement:dict:add:use',
          editView: 'operation:system:permissions:dictManagement:dict:edit:view',
          editUse: 'operation:system:permissions:dictManagement:dict:edit:use',
          deleteView: 'operation:system:permissions:dictManagement:dict:delete:view',
          deleteUse: 'operation:system:permissions:dictManagement:dict:delete:use',
          batchAddView: 'operation:system:permissions:dictManagement:dict:batchAdd:view',
          batchAddUse: 'operation:system:permissions:dictManagement:dict:batchAdd:use'
        }
      }
    }
  }
}
