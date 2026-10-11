import React, { useMemo } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import { FiPhone } from 'react-icons/fi';
import { 
  HiHome, 
  HiOutlineHome, 
  HiBuildingOffice2, 
  HiOutlineBuildingOffice2, 
  HiCalendarDays, 
  HiOutlineCalendarDays,
  HiOutlineIdentification 
} from 'react-icons/hi2';

export function MobileNav({ onOpenMedicalId }: { onOpenMedicalId?: () => void }) {
  const router = useRouterState();
  const currentPath = router.location.pathname;

  // Calculate dynamic active index (0, 1, 2)
  const activeIndex = useMemo(() => {
    if (currentPath === '/walk-in') return 1;
    if (currentPath === '/visits') return 2;
    return 0; // default Home
  }, [currentPath]);

  return (
    <div className="fixed bottom-5 left-0 right-0 z-50 px-2 sm:px-4 flex items-center justify-center pointer-events-none pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-center gap-2.5 sm:gap-3 w-full max-w-[380px] justify-between pointer-events-auto shrink-0">
        
        {/* LEFT DIV: Standalone Profile / Medical ID Upload or Add */}
        <div className="shrink-0 flex items-center justify-center">
          <button
            onClick={onOpenMedicalId}
            className="h-16 w-16 rounded-full bg-amber-500/20 backdrop-blur-2xl border border-amber-300/40 text-amber-500 dark:text-amber-300 font-black flex flex-col items-center justify-center shadow-[0_12px_40px_rgba(245,158,11,0.25),inset_0_1px_1px_rgba(255,255,255,0.4)] active:scale-90 transition-all duration-300 hover:bg-amber-500/30 group"
            aria-label="Upload or Add Profile (Medical ID)"
            title="Profile / Medical ID"
          >
            <HiOutlineIdentification className="h-7 w-7 shrink-0 transition-transform duration-300" />
          </button>
        </div>

        {/* CENTER PILL: Grid-aligned Glassmorphic Floating Nav */}
        <nav className="relative flex-1 h-16 rounded-full bg-background/40 backdrop-blur-2xl border border-white/40 dark:border-white/15 shadow-[0_12px_40px_rgba(0,0,0,0.18),inset_0_1px_1px_rgba(255,255,255,0.3)] grid grid-cols-3 place-items-center">
          
          {/* HOME */}
          <Link
            to="/"
            className="relative z-10 flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300"
            aria-label="Home"
          >
            <div className={`flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300 ${
              activeIndex === 0
                ? 'bg-black text-white dark:bg-white dark:text-black border-2 border-black dark:border-white scale-105 shadow-md'
                : 'border-2 border-transparent text-muted-foreground/60 hover:text-foreground'
            }`}>
              {activeIndex === 0 ? (
                <HiHome className="h-6 w-6 shrink-0" />
              ) : (
                <HiOutlineHome className="h-6 w-6 shrink-0" />
              )}
            </div>
          </Link>

          {/* CLINICS */}
          <Link
            to="/walk-in"
            className="relative z-10 flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300"
            aria-label="Walk-In Clinics"
          >
            <div className={`flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300 ${
              activeIndex === 1
                ? 'bg-black text-white dark:bg-white dark:text-black border-2 border-black dark:border-white scale-105 shadow-md'
                : 'border-2 border-transparent text-muted-foreground/60 hover:text-foreground'
            }`}>
              {activeIndex === 1 ? (
                <HiBuildingOffice2 className="h-6 w-6 shrink-0" />
              ) : (
                <HiOutlineBuildingOffice2 className="h-6 w-6 shrink-0" />
              )}
            </div>
          </Link>

          {/* VISITS */}
          <Link
            to={"/visits" as any}
            search={{ tab: 'upcoming' } as any}
            className="relative z-10 flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300"
            aria-label="My Visits"
          >
            <div className={`flex items-center justify-center h-12 w-12 shrink-0 rounded-full transition-all duration-300 ${
              activeIndex === 2
                ? 'bg-black text-white dark:bg-white dark:text-black border-2 border-black dark:border-white scale-105 shadow-md'
                : 'border-2 border-transparent text-muted-foreground/60 hover:text-foreground'
            }`}>
              {activeIndex === 2 ? (
                <HiCalendarDays className="h-6 w-6 shrink-0" />
              ) : (
                <HiOutlineCalendarDays className="h-6 w-6 shrink-0" />
              )}
            </div>
          </Link>

        </nav>

        {/* RIGHT CIRCLE: Glassmorphic Floating Emergency Call Circle */}
        <a
          href="tel:112"
          className="h-16 w-16 rounded-full bg-[#D92D20]/80 backdrop-blur-2xl border border-red-400/50 text-white font-black flex items-center justify-center shadow-[0_12px_40px_rgba(217,45,32,0.45),inset_0_1px_1px_rgba(255,255,255,0.4)] shrink-0 active:scale-90 transition-all duration-300 hover:bg-[#D92D20] group"
          aria-label="Call 112 Emergency"
        >
          <FiPhone className="h-7 w-7 shrink-0 animate-pulse transition-transform duration-300" />
        </a>

      </div>
    </div>
  );
}
