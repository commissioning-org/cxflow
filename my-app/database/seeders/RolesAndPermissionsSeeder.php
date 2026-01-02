<?php

namespace Database\Seeders;

use App\Models\Role;
use App\Models\Permission;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class RolesAndPermissionsSeeder extends Seeder
{
    /**
     * Permission definitions grouped by category.
     */
    protected array $permissions = [
        'users' => [
            'users.view' => 'View users',
            'users.create' => 'Create users',
            'users.update' => 'Update users',
            'users.delete' => 'Delete users',
            'users.ban' => 'Ban/suspend users',
            'users.impersonate' => 'Impersonate users',
        ],
        'roles' => [
            'roles.view' => 'View roles',
            'roles.create' => 'Create roles',
            'roles.update' => 'Update roles',
            'roles.delete' => 'Delete roles',
            'roles.assign' => 'Assign roles to users',
        ],
        'settings' => [
            'settings.view' => 'View settings',
            'settings.update' => 'Update settings',
        ],
        'content' => [
            'content.view' => 'View content',
            'content.create' => 'Create content',
            'content.update' => 'Update content',
            'content.delete' => 'Delete content',
            'content.publish' => 'Publish content',
        ],
        'reports' => [
            'reports.view' => 'View reports',
            'reports.export' => 'Export reports',
        ],
        'api' => [
            'api.access' => 'Access API',
            'assistant.use' => 'Use assistant API',
            'api.tokens.manage' => 'Manage API tokens',
        ],
    ];

    /**
     * Role definitions with their permissions.
     */
    protected array $roles = [
        User::ROLE_USER => [
            'display_name' => 'User',
            'description' => 'Standard user with basic permissions',
            'level' => 1,
            'permissions' => [
                'content.view',
                'api.access',
            ],
        ],
        User::ROLE_MODERATOR => [
            'display_name' => 'Moderator',
            'description' => 'Moderator with content management permissions',
            'level' => 50,
            'permissions' => [
                'users.view',
                'content.view',
                'content.create',
                'content.update',
                'content.delete',
                'reports.view',
                'api.access',
                'assistant.use',
            ],
        ],
        User::ROLE_ADMIN => [
            'display_name' => 'Administrator',
            'description' => 'Administrator with full management permissions',
            'level' => 100,
            'permissions' => [
                'users.view',
                'users.create',
                'users.update',
                'users.delete',
                'users.ban',
                'roles.view',
                'roles.assign',
                'settings.view',
                'settings.update',
                'content.view',
                'content.create',
                'content.update',
                'content.delete',
                'content.publish',
                'reports.view',
                'reports.export',
                'api.access',
                'assistant.use',
                'api.tokens.manage',
            ],
        ],
        User::ROLE_SUPER_ADMIN => [
            'display_name' => 'Super Administrator',
            'description' => 'Super admin with all permissions',
            'level' => 999,
            'permissions' => '*', // All permissions
        ],
    ];

    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $this->createPermissions();
        $this->createRoles();
        $this->createSuperAdmin();
    }

    /**
     * Create all permissions.
     */
    protected function createPermissions(): void
    {
        foreach ($this->permissions as $group => $permissions) {
            foreach ($permissions as $name => $displayName) {
                Permission::firstOrCreate(
                    ['name' => $name],
                    [
                        'display_name' => $displayName,
                        'description' => $displayName,
                        'group' => $group,
                    ]
                );
            }
        }

        $this->command->info('Permissions created successfully.');
    }

    /**
     * Create all roles and assign permissions.
     */
    protected function createRoles(): void
    {
        $allPermissionIds = Permission::pluck('id');

        foreach ($this->roles as $name => $config) {
            $role = Role::firstOrCreate(
                ['name' => $name],
                [
                    'display_name' => $config['display_name'],
                    'description' => $config['description'],
                    'level' => $config['level'],
                ]
            );

            // Assign permissions
            if ($config['permissions'] === '*') {
                $role->permissions()->sync($allPermissionIds);
            } else {
                $permissionIds = Permission::whereIn('name', $config['permissions'])
                    ->pluck('id');
                $role->permissions()->sync($permissionIds);
            }
        }

        $this->command->info('Roles created and permissions assigned successfully.');
    }

    /**
     * Create the initial super admin user.
     */
    protected function createSuperAdmin(): void
    {
        $email = env('ADMIN_EMAIL', 'admin@example.com');
        $password = env('ADMIN_PASSWORD', 'password');

        $admin = User::firstOrCreate(
            ['email' => $email],
            [
                'name' => 'Super Admin',
                'password' => Hash::make($password),
                'email_verified_at' => now(),
                'status' => User::STATUS_ACTIVE,
            ]
        );

        $superAdminRole = Role::where('name', User::ROLE_SUPER_ADMIN)->first();
        
        if ($superAdminRole && !$admin->roles()->where('role_id', $superAdminRole->id)->exists()) {
            $admin->roles()->attach($superAdminRole->id);
        }

        $this->command->info("Super admin created: {$email}");
    }
}
