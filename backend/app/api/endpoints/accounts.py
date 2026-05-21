import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models.account import Account, AccountUser, AccountZone
from app.models.user import User, UserRole
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountUserAdd,
    AccountUserResponse,
    AccountZoneAdd,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


async def _build_response(db: DbDep, account: Account) -> AccountResponse:
    zones = (
        await db.execute(select(AccountZone.zone_name).where(AccountZone.account_id == account.id))
    ).scalars().all()
    user_rows = (
        await db.execute(
            select(AccountUser, User)
            .join(User, AccountUser.user_id == User.id)
            .where(AccountUser.account_id == account.id)
        )
    ).all()
    return AccountResponse(
        id=account.id,
        name=account.name,
        description=account.description,
        created_at=account.created_at,
        zone_names=list(zones),
        users=[
            AccountUserResponse(user_id=au.user_id, username=u.username, role=au.role)
            for au, u in user_rows
        ],
    )


def _require_admin(current_user: User) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")


@router.get("", response_model=list[AccountResponse])
async def list_accounts(current_user: CurrentUser, db: DbDep) -> list[AccountResponse]:
    is_admin = current_user.role in (UserRole.superadmin, UserRole.admin)

    if is_admin:
        accounts = (await db.execute(select(Account).order_by(Account.name))).scalars().all()
    else:
        accounts = (
            await db.execute(
                select(Account)
                .join(AccountUser, Account.id == AccountUser.account_id)
                .where(AccountUser.user_id == current_user.id)
                .order_by(Account.name)
            )
        ).scalars().all()

    return [await _build_response(db, a) for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, current_user: CurrentUser, db: DbDep) -> AccountResponse:
    _require_admin(current_user)

    existing = (
        await db.execute(select(Account).where(Account.name == body.name))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account name already exists")

    account = Account(name=body.name, description=body.description)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return await _build_response(db, account)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> AccountResponse:
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    is_admin = current_user.role in (UserRole.superadmin, UserRole.admin)
    if not is_admin:
        membership = (
            await db.execute(
                select(AccountUser).where(
                    AccountUser.account_id == account_id,
                    AccountUser.user_id == current_user.id,
                )
            )
        ).scalar_one_or_none()
        if not membership:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    return await _build_response(db, account)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    current_user: CurrentUser,
    db: DbDep,
) -> AccountResponse:
    _require_admin(current_user)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    if body.name is not None:
        conflict = (
            await db.execute(
                select(Account).where(Account.name == body.name, Account.id != account_id)
            )
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Account name already exists")
        account.name = body.name

    if body.description is not None:
        account.description = body.description

    await db.commit()
    await db.refresh(account)
    return await _build_response(db, account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> None:
    _require_admin(current_user)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    await db.delete(account)
    await db.commit()


@router.post("/{account_id}/zones", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def add_zone(
    account_id: uuid.UUID,
    body: AccountZoneAdd,
    current_user: CurrentUser,
    db: DbDep,
) -> AccountResponse:
    _require_admin(current_user)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    existing = (
        await db.execute(
            select(AccountZone).where(
                AccountZone.account_id == account_id,
                AccountZone.zone_name == body.zone_name,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zone already in this account")

    db.add(AccountZone(account_id=account_id, zone_name=body.zone_name))
    await db.commit()
    return await _build_response(db, account)


@router.delete("/{account_id}/zones", status_code=status.HTTP_204_NO_CONTENT)
async def remove_zone(
    account_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    zone_name: str = Query(..., description="Zone name to remove (e.g. example.com.)"),
) -> None:
    _require_admin(current_user)

    record = (
        await db.execute(
            select(AccountZone).where(
                AccountZone.account_id == account_id,
                AccountZone.zone_name == zone_name,
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found in this account")

    await db.delete(record)
    await db.commit()


@router.post("/{account_id}/users", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def add_user(
    account_id: uuid.UUID,
    body: AccountUserAdd,
    current_user: CurrentUser,
    db: DbDep,
) -> AccountResponse:
    _require_admin(current_user)

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    user = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    existing = (
        await db.execute(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == body.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already in this account")

    db.add(AccountUser(account_id=account_id, user_id=body.user_id, role=body.role))
    await db.commit()
    return await _build_response(db, account)


@router.delete("/{account_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> None:
    _require_admin(current_user)

    record = (
        await db.execute(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this account")

    await db.delete(record)
    await db.commit()
