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
        userManagement: {
          users: {
            view: 'page:system:permissions:userManagement:users:view',
            addUse: 'page:system:permissions:userManagement:users:add:use',
            deleteUse: 'page:system:permissions:userManagement:users:delete:use',
            detailUse: 'page:system:permissions:userManagement:users:detail:use',
            editUse: 'page:system:permissions:userManagement:users:edit:use'
          }
        },
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
    search: {
      templateManagement: {
        templates: {
          listView: 'operation:search:templateManagement:templates:view',
          applyView: 'operation:search:templateManagement:templates:apply:view',
          applyUse: 'operation:search:templateManagement:templates:apply:use',
          addView: 'operation:search:templateManagement:templates:add:view',
          addUse: 'operation:search:templateManagement:templates:add:use',
          overwriteView: 'operation:search:templateManagement:templates:overwrite:view',
          overwriteUse: 'operation:search:templateManagement:templates:overwrite:use',
          editView: 'operation:search:templateManagement:templates:edit:view',
          editUse: 'operation:search:templateManagement:templates:edit:use',
          deleteView: 'operation:search:templateManagement:templates:delete:view',
          deleteUse: 'operation:search:templateManagement:templates:delete:use'
        }
      },
      results: {
        detailView: 'operation:search:results:detail:view',
        highlightUse: 'operation:search:results:highlight:use',
        unhighlightUse: 'operation:search:results:unhighlight:use',
        analysisView: 'operation:search:results:analysis:view'
      }
    },
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
