"""
Security management for Apache Superset.

Provides security and access control:
- User management
- Role management
- Permission management
- Row-level security
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


@dataclass
class Permission:
    """Represents a Superset permission."""
    id: int
    name: str
    view_menu: Optional[str] = None
    view_menu_id: Optional[int] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Permission:
        """Create from API response."""
        return cls(
            id=data.get("id", 0),
            name=data.get("permission", {}).get("name", "") if isinstance(data.get("permission"), dict) else data.get("name", ""),
            view_menu=data.get("view_menu", {}).get("name") if isinstance(data.get("view_menu"), dict) else None,
            view_menu_id=data.get("view_menu", {}).get("id") if isinstance(data.get("view_menu"), dict) else None,
        )
    
    def __str__(self) -> str:
        if self.view_menu:
            return f"{self.name} on {self.view_menu}"
        return self.name


@dataclass
class Role:
    """Represents a Superset role."""
    id: int
    name: str
    permissions: List[Permission] = field(default_factory=list)
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Role:
        """Create from API response."""
        result = data.get("result", data)
        
        permissions = [
            Permission.from_api(p)
            for p in result.get("permissions", [])
        ]
        
        return cls(
            id=result.get("id", 0),
            name=result.get("name", ""),
            permissions=permissions,
        )
    
    def has_permission(self, permission_name: str, view_menu: Optional[str] = None) -> bool:
        """Check if role has a specific permission."""
        for perm in self.permissions:
            if perm.name == permission_name:
                if view_menu is None or perm.view_menu == view_menu:
                    return True
        return False


@dataclass
class User:
    """Represents a Superset user."""
    id: int
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    active: bool = True
    
    # Roles
    roles: List[Role] = field(default_factory=list)
    
    # Timestamps
    created_on: Optional[datetime] = None
    changed_on: Optional[datetime] = None
    last_login: Optional[datetime] = None
    login_count: int = 0
    fail_login_count: int = 0
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> User:
        """Create from API response."""
        result = data.get("result", data)
        
        roles = []
        for role_data in result.get("roles", []):
            if isinstance(role_data, dict):
                roles.append(Role(
                    id=role_data.get("id", 0),
                    name=role_data.get("name", ""),
                ))
        
        return cls(
            id=result.get("id", 0),
            username=result.get("username", ""),
            email=result.get("email"),
            first_name=result.get("first_name"),
            last_name=result.get("last_name"),
            active=result.get("active", True),
            roles=roles,
            login_count=result.get("login_count", 0),
            fail_login_count=result.get("fail_login_count", 0),
        )
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else self.username
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(r.name == role_name for r in self.roles)


@dataclass
class RowLevelSecurityFilter:
    """Row-level security filter."""
    id: int
    name: str
    filter_type: str  # "Regular" or "Base"
    clause: str
    tables: List[int] = field(default_factory=list)
    roles: List[int] = field(default_factory=list)
    group_key: Optional[str] = None
    description: Optional[str] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> RowLevelSecurityFilter:
        """Create from API response."""
        result = data.get("result", data)
        
        return cls(
            id=result.get("id", 0),
            name=result.get("name", ""),
            filter_type=result.get("filter_type", "Regular"),
            clause=result.get("clause", ""),
            tables=[t.get("id") for t in result.get("tables", []) if isinstance(t, dict)],
            roles=[r.get("id") for r in result.get("roles", []) if isinstance(r, dict)],
            group_key=result.get("group_key"),
            description=result.get("description"),
        )


class SecurityManager:
    """
    High-level security management.
    
    Usage:
        manager = SecurityManager(client)
        
        # Get current user
        me = manager.get_current_user()
        
        # List roles
        roles = manager.list_roles()
        
        # Create role
        role = manager.create_role("Analyst", permissions=[...])
        
        # Manage users
        users = manager.list_users()
        manager.add_user_to_role(user_id, role_id)
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    # User management
    
    def get_current_user(self) -> User:
        """Get current authenticated user."""
        result = self.client.get_current_user()
        return User.from_api(result)
    
    def list_users(
        self,
        page: int = 0,
        page_size: int = 100,
        active_only: bool = False,
    ) -> List[User]:
        """List all users."""
        result = self.client.get_users(page=page, page_size=page_size)
        
        users = []
        for item in result.get("result", []):
            user = User.from_api({"result": item})
            if not active_only or user.active:
                users.append(user)
        
        return users
    
    def get_user(self, user_id: int) -> User:
        """Get user by ID."""
        result = self.client.get_user(user_id)
        return User.from_api(result)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        users = self.list_users()
        for user in users:
            if user.username == username:
                return user
        return None
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        roles: Optional[List[int]] = None,
    ) -> User:
        """Create a new user."""
        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "roles": roles or [],
            "active": True,
        }
        
        result = self.client.create_user(user_data)
        return self.get_user(result.get("id"))
    
    def update_user(
        self,
        user_id: int,
        **kwargs,
    ) -> User:
        """Update an existing user."""
        self.client.update_user(user_id, kwargs)
        return self.get_user(user_id)
    
    def deactivate_user(self, user_id: int) -> User:
        """Deactivate a user."""
        return self.update_user(user_id, active=False)
    
    def activate_user(self, user_id: int) -> User:
        """Activate a user."""
        return self.update_user(user_id, active=True)
    
    def reset_user_password(self, user_id: int, new_password: str) -> User:
        """Reset user password."""
        return self.update_user(user_id, password=new_password)
    
    def add_user_to_role(self, user_id: int, role_id: int) -> User:
        """Add a user to a role."""
        user = self.get_user(user_id)
        role_ids = [r.id for r in user.roles]
        
        if role_id not in role_ids:
            role_ids.append(role_id)
            return self.update_user(user_id, roles=role_ids)
        
        return user
    
    def remove_user_from_role(self, user_id: int, role_id: int) -> User:
        """Remove a user from a role."""
        user = self.get_user(user_id)
        role_ids = [r.id for r in user.roles if r.id != role_id]
        return self.update_user(user_id, roles=role_ids)
    
    # Role management
    
    def list_roles(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> List[Role]:
        """List all roles."""
        result = self.client.get_roles(page=page, page_size=page_size)
        
        roles = []
        for item in result.get("result", []):
            roles.append(Role.from_api({"result": item}))
        
        return roles
    
    def get_role(self, role_id: int) -> Role:
        """Get role by ID."""
        result = self.client.get_role(role_id)
        return Role.from_api(result)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        roles = self.list_roles()
        for role in roles:
            if role.name == name:
                return role
        return None
    
    def create_role(
        self,
        name: str,
        permissions: Optional[List[int]] = None,
    ) -> Role:
        """Create a new role."""
        role_data = {
            "name": name,
            "permissions": permissions or [],
        }
        
        result = self.client.create_role(role_data)
        return self.get_role(result.get("id"))
    
    def update_role(
        self,
        role_id: int,
        **kwargs,
    ) -> Role:
        """Update an existing role."""
        self.client.update_role(role_id, kwargs)
        return self.get_role(role_id)
    
    def delete_role(self, role_id: int) -> bool:
        """Delete a role."""
        try:
            self.client.delete_role(role_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete role {role_id}: {e}")
            return False
    
    def clone_role(self, role_id: int, new_name: str) -> Role:
        """Clone an existing role."""
        original = self.get_role(role_id)
        
        permission_ids = [p.id for p in original.permissions]
        return self.create_role(new_name, permissions=permission_ids)
    
    # Permission management
    
    def list_permissions(self) -> List[Permission]:
        """List all available permissions."""
        result = self.client.get_permissions()
        
        permissions = []
        for item in result.get("result", []):
            permissions.append(Permission.from_api(item))
        
        return permissions
    
    def add_permission_to_role(
        self,
        role_id: int,
        permission_id: int,
    ) -> Role:
        """Add a permission to a role."""
        role = self.get_role(role_id)
        permission_ids = [p.id for p in role.permissions]
        
        if permission_id not in permission_ids:
            permission_ids.append(permission_id)
            return self.update_role(role_id, permissions=permission_ids)
        
        return role
    
    def remove_permission_from_role(
        self,
        role_id: int,
        permission_id: int,
    ) -> Role:
        """Remove a permission from a role."""
        role = self.get_role(role_id)
        permission_ids = [p.id for p in role.permissions if p.id != permission_id]
        return self.update_role(role_id, permissions=permission_ids)
    
    # Row-level security
    
    def list_rls_filters(
        self,
        page: int = 0,
        page_size: int = 100,
    ) -> List[RowLevelSecurityFilter]:
        """List all row-level security filters."""
        result = self.client.get_rls_filters(page=page, page_size=page_size)
        
        filters = []
        for item in result.get("result", []):
            filters.append(RowLevelSecurityFilter.from_api({"result": item}))
        
        return filters
    
    def create_rls_filter(
        self,
        name: str,
        clause: str,
        tables: List[int],
        roles: List[int],
        filter_type: str = "Regular",
        group_key: Optional[str] = None,
        description: Optional[str] = None,
    ) -> RowLevelSecurityFilter:
        """Create a row-level security filter."""
        rls_data = {
            "name": name,
            "clause": clause,
            "tables": tables,
            "roles": roles,
            "filter_type": filter_type,
            "group_key": group_key,
            "description": description,
        }
        
        result = self.client.create_rls_filter(rls_data)
        return RowLevelSecurityFilter.from_api(result)
    
    def delete_rls_filter(self, filter_id: int) -> bool:
        """Delete a row-level security filter."""
        try:
            self.client.delete_rls_filter(filter_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete RLS filter {filter_id}: {e}")
            return False
