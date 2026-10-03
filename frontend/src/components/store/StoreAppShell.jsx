import {
  ArrowLeftRight,
  ClipboardList,
  LayoutGrid,
  LogOut,
  Package,
  Warehouse,
} from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { BrandLogo } from "../layout/Shell"
import { getStoreTab, STORE_TABS } from "../../constants/store"

const NAV_ICONS = {
  bins: LayoutGrid,
  inward: Package,
  issue: ArrowLeftRight,
  reports: ClipboardList,
}

export function StoreAppShell({
  activeTab,
  onTabChange,
  username,
  onLogout,
  children,
}) {
  const current = getStoreTab(activeTab)
  const initials = username?.slice(0, 2).toUpperCase() || "SK"

  return (
    <SidebarProvider defaultOpen>
      <Sidebar collapsible="icon" className="border-sidebar-border">
        <SidebarHeader className="border-b border-sidebar-border">
          <div className="flex items-center gap-3 px-2 py-3 group-data-[collapsible=icon]:justify-center">
            <BrandLogo size="sm" className="shrink-0 rounded-md" />
            <div className="min-w-0 group-data-[collapsible=icon]:hidden">
              <p className="truncate text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Rushab Industries
              </p>
              <p className="truncate text-sm font-bold text-sidebar-foreground">
                Store Keeper
              </p>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Store operations</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {STORE_TABS.map((tab) => {
                  const Icon = NAV_ICONS[tab.id]
                  return (
                    <SidebarMenuItem key={tab.id}>
                      <SidebarMenuButton
                        isActive={activeTab === tab.id}
                        onClick={() => onTabChange(tab.id)}
                        tooltip={tab.label}
                      >
                        <Icon />
                        <span>{tab.label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter className="border-t border-sidebar-border">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={onLogout} tooltip="Sign out">
                <LogOut />
                <span>Sign out</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-w-0 bg-transparent">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border/60 bg-background/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/75">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:inline-flex">
                <Warehouse className="mr-1 inline size-3.5" />
                Store
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:inline-flex" />
              <BreadcrumbItem>
                <BreadcrumbPage>{current.label}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold text-foreground">{username}</p>
              <p className="text-xs text-muted-foreground">Store Keeper</p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring">
                <Avatar className="size-9 border border-brand-200">
                  <AvatarFallback className="bg-brand-100 text-xs font-bold text-brand-700">
                    {initials}
                  </AvatarFallback>
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuLabel>{username}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onLogout}>
                  <LogOut className="size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-6 p-4 md:p-6 min-w-0">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              {current.title}
            </h1>
            <p className="text-sm text-muted-foreground">
              Material inward, bin tracking, and issue management
            </p>
          </div>
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function StoreSectionCard({ title, description, children, action }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/90 shadow-sm backdrop-blur-sm">
      <div className="flex flex-col gap-3 border-b border-border bg-muted/40 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground">{title}</h2>
          {description && (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {action}
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}
