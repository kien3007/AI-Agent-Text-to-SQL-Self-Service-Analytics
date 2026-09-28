import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import MainApp from '@/components/MainApp';
import { SidebarTab } from '@/components/Sidebar';

export default async function Page() {
  const cookieStore = await cookies();
  const token = cookieStore.get('jwt_token')?.value;

  if (!token) {
    redirect('/login');
  }

  const rawTab = cookieStore.get('sana_active_tab')?.value;
  const initialTab: SidebarTab =
    rawTab && ['chat', 'catalog', 'lineage', 'benchmark'].includes(rawTab)
      ? (rawTab as SidebarTab)
      : 'chat';

  return <MainApp initialTab={initialTab} />;
}
