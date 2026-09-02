import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Play, Download, Menu, X, Check, Compass, Wind, Moon, GraduationCap, Flame, User, Flower2, BookOpen, ExternalLink, Star, Truck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import InstagramReels from "@/components/InstagramReels";
import FreeClassRibbon from "@/components/FreeClassRibbon";
import Logo from "@/components/Logo";
import LanguageToggle from "@/components/LanguageToggle";
import InlineSignup from "@/components/InlineSignup";
import { FeatureStrip, StatsBar, ValueProps, FAQ } from "@/components/MarketingSections";
import HeroTestimonial from "@/components/HeroTestimonial";
import AssistantWidget from "@/components/AssistantWidget";

const HERO = "https://images.squarespace-cdn.com/content/v1/620bca2d082bbf5542408178/6b55c6a0-8c26-4670-8cb7-68a45f7371fb/TonySanchez-head-to-knee.png";

function isStandalone() {
  return typeof window !== "undefined" && (window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true);
}

function Nav({ onOpenApp }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { t } = useTranslation();
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const items = [
    { href: "#story", label: t("marketing.nav_story") },
    { href: "#programs", label: t("marketing.nav_programs") },
    { href: "#retreats", label: t("marketing.nav_retreats") },
    { href: "#faq", label: t("marketing.nav_faq") },
    { href: "#join", label: t("marketing.nav_join") },
  ];
  return (
    <header
      data-testid="marketing-nav"
      className={`fixed inset-x-0 z-50 transition top-10 ${scrolled ? "bg-[#FAFAF7]/90 backdrop-blur-xl border-b border-[#E5E6DF]" : ""}`}
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
        <a href="#top" className="flex items-center" data-testid="marketing-logo">
          <Logo className="h-[60px] w-[60px] sm:h-[79px] sm:w-[79px]" />
        </a>
        <nav className="hidden lg:flex items-center gap-8" data-testid="marketing-nav-links">
          {items.map((i) => (
            <a key={i.href} href={i.href} className="text-sm text-[#545E56] hover:text-[#B25A45] transition">{i.label}</a>
          ))}
        </nav>
        <div className="hidden lg:flex items-center gap-3">
          <LanguageToggle />
          <Link to="/login" data-testid="nav-signin" className="text-sm text-[#545E56] hover:text-[#B25A45] transition">{t("common.signIn")}</Link>
          <button onClick={onOpenApp} data-testid="nav-open-app" className="pill pill-primary !py-2 !px-4 !text-[13px]">
            {t("marketing.open_app")} <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <button onClick={() => setOpen((o) => !o)} data-testid="nav-menu-toggle" className="lg:hidden h-9 w-9 rounded-full border border-[#E5E6DF] flex items-center justify-center">
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>
      {open && (
        <div className="lg:hidden bg-[#FAFAF7] border-b border-[#E5E6DF] px-4 sm:px-6 py-4" data-testid="mobile-menu">
          <ul className="space-y-3">
            {items.map((i) => (
              <li key={i.href}><a href={i.href} onClick={() => setOpen(false)} className="block py-2 text-[#1C221F] font-medium">{i.label}</a></li>
            ))}
            <li className="pt-2 border-t border-[#E5E6DF]">
              <Link to="/login" data-testid="mobile-nav-signin" className="block py-2 text-[#1C221F] font-medium">{t("common.signIn")}</Link>
            </li>
            <li className="pt-1"><LanguageToggle /></li>
            <li><button onClick={onOpenApp} data-testid="mobile-nav-open-app" className="pill pill-primary w-full mt-2">{t("marketing.open_app")} <ArrowRight className="h-4 w-4" /></button></li>
          </ul>
        </div>
      )}
    </header>
  );
}

function Hero({ onOpenApp }) {
  const { t } = useTranslation();
  return (
    <section id="top" className="relative overflow-hidden pt-24 sm:pt-28 lg:pt-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 grid lg:grid-cols-2 gap-8 lg:gap-16 items-center lg:min-h-[80vh]">
        <div className="animate-fade-up order-2 lg:order-1">
          <div className="eyebrow mb-3 sm:mb-4">{t("mkt.hero_eyebrow")}</div>
          <h1 className="serif text-4xl sm:text-5xl lg:text-7xl leading-[1.02] font-medium mb-4 sm:mb-6" data-testid="hero-title">
            {t("mkt.hero_t1")}<br/>{t("mkt.hero_t2")}<br/><span className="text-[#B25A45]">{t("mkt.hero_t3")}</span>
          </h1>
          <p className="text-base sm:text-lg text-[#545E56] leading-relaxed mb-6 sm:mb-8 max-w-md">
            {t("mkt.hero_sub")}
          </p>
          <div className="flex flex-wrap gap-2 sm:gap-3">
            <a href="#join" data-testid="hero-cta-signup" className="pill pill-primary">
              {t("mkt.create_account")} <ArrowRight className="h-4 w-4" />
            </a>
            <button onClick={onOpenApp} data-testid="hero-cta-open-app" className="pill pill-ghost">
              <Download className="h-4 w-4" /> {t("marketing.open_app")}
            </button>
          </div>
          <div className="mt-8 sm:mt-10 flex items-center gap-6 sm:gap-8">
            {[["50+", t("mkt.stat_years")], ["3", t("mkt.stat_programs")], ["4", t("mkt.stat_retreats")]].map(([n, l]) => (
              <div key={l}>
                <div className="serif text-2xl sm:text-3xl leading-none">{n}</div>
                <div className="eyebrow mt-1 !text-[10px]">{l}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative animate-fade-up animate-delay-2 order-1 lg:order-2 max-w-md mx-auto lg:max-w-none w-full">
          <div className="relative aspect-[3/4] rounded-2xl sm:rounded-3xl overflow-hidden bg-[#F2F2EC]">
            <img src={HERO} alt="Tony Sanchez in head-to-knee pose" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-0 grain"></div>
          </div>
          <div className="hidden lg:block absolute -left-6 -bottom-6 w-52 rounded-2xl bg-[#1C221F] text-[#FAFAF7] p-5 shadow-2xl">
            <div className="eyebrow !text-[#B25A45]">{t("mkt.live_now")}</div>
            <div className="text-sm mt-1 font-semibold">{t("mkt.hero_card_title")}</div>
            <div className="text-xs text-white/60 mt-1">{t("mkt.hero_card_time")}</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Story() {
  const { t } = useTranslation();
  return (
    <section id="story" className="mx-auto max-w-6xl px-4 sm:px-6 py-14 sm:py-20 lg:py-24 grid md:grid-cols-3 gap-8 md:gap-12">
      <div className="md:col-span-1">
        <div className="eyebrow mb-3">{t("mkt.story_eyebrow")}</div>
        <h2 className="serif text-3xl sm:text-4xl leading-tight">{t("mkt.story_t1")}<br/>{t("mkt.story_t2")}</h2>
      </div>
      <div className="md:col-span-2 space-y-5 sm:space-y-6 text-[#545E56] leading-relaxed">
        <p className="text-base sm:text-lg">{t("mkt.story_p1")}</p>
        <p>{t("mkt.story_p2")}</p>
        <p className="italic serif text-lg sm:text-xl text-[#1C221F]">{t("mkt.story_quote")}</p>
        <div className="pt-2 sm:pt-4">
          <a href="#programs" className="text-sm font-semibold text-[#B25A45] hover:underline">{t("mkt.story_link")}</a>
        </div>
      </div>
    </section>
  );
}

function Programs() {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api.get("/programs")
      .then(({ data }) => {
        const programs = Array.isArray(data)
          ? data
          : Array.isArray(data?.programs)
            ? data.programs
            : Array.isArray(data?.data)
              ? data.data
              : Array.isArray(data?.items)
                ? data.items
                : [];
        setRows(programs);
      })
      .catch(() => setRows([]));
  }, []);
  return (
    <section id="programs" className="bg-[#1C221F] text-[#FAFAF7] py-14 sm:py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="max-w-lg mb-8 sm:mb-12">
          <div className="eyebrow !text-[#B25A45] mb-3">{t("mkt.programs_eyebrow")}</div>
          <h2 className="serif text-3xl sm:text-4xl leading-tight mb-4">{t("mkt.programs_title")}</h2>
          <p className="text-white/70 leading-relaxed text-sm sm:text-base">{t("mkt.programs_sub")}</p>
        </div>
        <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6" data-testid="marketing-programs">
          {rows.map((p) => (
            <li key={p.id}>
              <Link
                to={`/programs/${p.id}`}
                data-testid={`marketing-program-${p.id}`}
                className="group block h-full rounded-3xl overflow-hidden bg-[#0F1211] border border-white/10 transition-all duration-300 hover:border-[#B25A45] hover:-translate-y-1"
              >
                {p.cover_image && (
                  <div className="aspect-[4/5] overflow-hidden">
                    <img src={p.cover_image} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                  </div>
                )}
                <div className="p-6">
                  <div className="eyebrow !text-[#B25A45]">{p.level}</div>
                  <div className="serif text-2xl mt-1">{p.title}</div>
                  <div className="text-xs text-white/60 mt-2">{p.duration_weeks} {t("mkt.weeks")} · €{Math.round(p.price)}</div>
                  <p className="text-sm text-white/70 mt-4 clamp-3 leading-relaxed">{p.description}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#B25A45]">
                    {t("mkt.view_program")} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Retreats() {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/workshops").then(({ data }) => setRows((data || []).slice(0, 2))).catch(() => {}); }, []);
  return (
    <section id="retreats" className="mx-auto max-w-6xl px-4 sm:px-6 py-14 sm:py-20 lg:py-24">
      <div className="grid md:grid-cols-2 gap-6 md:gap-10 items-end mb-8 sm:mb-12">
        <div>
          <div className="eyebrow mb-3">{t("mkt.retreats_eyebrow")}</div>
          <h2 className="serif text-3xl sm:text-4xl leading-tight">{t("mkt.retreats_t1")}<br/>{t("mkt.retreats_t2")}</h2>
        </div>
        <p className="text-[#545E56] leading-relaxed text-sm sm:text-base">{t("mkt.retreats_sub")}</p>
      </div>
      <ul className="grid md:grid-cols-2 gap-4 sm:gap-6" data-testid="marketing-retreats">
        {rows.map((w) => (
          <li key={w.id}>
            <Link
              to={`/workshops/${w.id}`}
              data-testid={`marketing-retreat-${w.id}`}
              className="group block h-full rounded-3xl overflow-hidden bg-white border border-[#E5E6DF] transition-all duration-300 hover:border-[#B25A45] hover:-translate-y-1"
            >
              {w.cover_image && (
                <div className="aspect-[16/10] overflow-hidden bg-[#F2F2EC]">
                  <img src={w.cover_image} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                </div>
              )}
              <div className="p-6">
                <div className="eyebrow">{w.system}</div>
                <div className="serif text-2xl mt-1 leading-tight">{w.title}</div>
                <p className="text-sm text-[#6B7269] mt-2 leading-relaxed clamp-2">{w.description}</p>
                <div className="mt-4 flex items-center justify-between">
                  <div className="text-sm text-[#545E56]">{new Date(w.start_date).toLocaleDateString(undefined, { month: "long", year: "numeric" })}</div>
                  <div className="text-[#B25A45] font-semibold">€{w.deposit_eur ?? 500} {t("mkt.deposit")}</div>
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Testimonials() {
  const { t } = useTranslation();
  const testimonials = [
    { quote: t("tst.q1"), author: "María Castillo", role: t("tst.r1"), photo: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200&h=200&fit=crop&crop=faces" },
    { quote: t("tst.q2"), author: "James Ridley", role: t("tst.r2"), photo: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop&crop=faces" },
    { quote: t("tst.q3"), author: "Sofia Larsen", role: t("tst.r3"), photo: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&fit=crop&crop=faces" },
  ];
  return (
    <section id="testimonials" className="bg-[#F2F2EC] py-14 sm:py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="max-w-lg mb-8 sm:mb-12">
          <div className="eyebrow mb-3">{t("tst.eyebrow")}</div>
          <h2 className="serif text-3xl sm:text-4xl leading-tight">{t("tst.title")}</h2>
        </div>
        <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6" data-testid="marketing-testimonials">
          {testimonials.map((tm, i) => (
            <li key={i} className="rounded-2xl sm:rounded-3xl bg-[#FAFAF7] p-6 sm:p-8 flex flex-col">
              <div className="serif text-4xl text-[#B25A45] leading-none">"</div>
              <p className="text-[15px] text-[#1C221F] leading-relaxed mt-3 flex-1">{tm.quote}</p>
              <div className="mt-6 pt-4 border-t border-[#E5E6DF] flex items-center gap-3">
                <div className="h-11 w-11 rounded-full overflow-hidden bg-[#F2F2EC] shrink-0">
                  <img src={tm.photo} alt={tm.author} className="h-full w-full object-cover" loading="lazy" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{tm.author}</div>
                  <div className="text-xs text-[#6B7269] mt-0.5 truncate">{tm.role}</div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function AppCTA({ onOpenApp }) {
  const { t } = useTranslation();
  const features = [t("appf.1"), t("appf.2"), t("appf.3"), t("appf.4"), t("appf.5"), t("appf.6")];
  return (
    <section className="mx-auto max-w-6xl px-4 sm:px-6 py-14 sm:py-20 lg:py-24">
      <div className="rounded-2xl sm:rounded-3xl bg-[#1C221F] text-[#FAFAF7] p-6 sm:p-10 lg:p-16 grid md:grid-cols-2 gap-8 md:gap-10 items-center">
        <div>
          <div className="eyebrow !text-[#B25A45] mb-3">{t("mkt.appcta_eyebrow")}</div>
          <h2 className="serif text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">{t("mkt.appcta_t1")}<br/>{t("mkt.appcta_t2")}</h2>
          <p className="text-white/70 leading-relaxed mb-6 max-w-md text-sm sm:text-base">{t("mkt.appcta_sub")}</p>
          <div className="flex flex-wrap gap-3">
            <button onClick={onOpenApp} data-testid="cta-open-app-primary" className="pill !bg-[#B25A45] !text-white">
              <Download className="h-4 w-4" /> {t("marketing.open_app")}
            </button>
            <span className="text-xs text-white/50 self-center">iOS · Android · Desktop</span>
          </div>
        </div>
        <ul className="space-y-3" data-testid="app-features">
          {features.map((f) => (
            <li key={f} className="flex items-start gap-3">
              <div className="mt-0.5 h-5 w-5 rounded-full bg-[#B25A45] flex items-center justify-center shrink-0">
                <Check className="h-3 w-3 text-white" />
              </div>
              <span className="text-white/85">{f}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Footer() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [subbed, setSubbed] = useState(false);
  const subscribe = async (e) => {
    e.preventDefault();
    try {
      await api.post("/submissions/newsletter", { email });
      setSubbed(true);
    } catch { setSubbed(true); }
  };
  return (
    <footer className="bg-[#1C221F] text-[#FAFAF7] py-12 sm:py-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 grid md:grid-cols-2 gap-8 md:gap-10">
        <div>
          <div className="mb-4">
            <Logo className="h-20 w-20 sm:h-24 sm:w-24" />
          </div>
          <p className="text-white/60 text-sm leading-relaxed max-w-sm">{t("mkt.footer_tagline")}</p>
          <a href="mailto:tony@tonysanchezyoga.com" className="text-sm text-[#B25A45] hover:underline mt-4 inline-block">tony@tonysanchezyoga.com</a>
        </div>
        <div>
          <div className="eyebrow !text-[#B25A45] mb-3">{t("mkt.stay_in_touch")}</div>
          <p className="text-sm text-white/60 mb-4">{t("mkt.newsletter_sub")}</p>
          {subbed ? (
            <div className="rounded-2xl bg-white/5 border border-white/10 p-4 text-sm text-white/80" data-testid="footer-newsletter-thanks">
              {t("mkt.newsletter_thanks")}
            </div>
          ) : (
            <form onSubmit={subscribe} className="flex gap-2" data-testid="footer-newsletter-form">
              <input
                required type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="footer-newsletter-email"
                placeholder="you@example.com"
                className="flex-1 rounded-full bg-white/10 border border-white/10 px-4 py-2.5 text-sm text-white placeholder:text-white/40 focus:outline-none focus:border-[#B25A45]"
              />
              <button type="submit" data-testid="footer-newsletter-submit" className="pill !bg-[#B25A45] !text-white !py-2 !px-4 !text-[13px]">{t("mkt.subscribe")}</button>
            </form>
          )}
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-4 sm:px-6 mt-8 sm:mt-12 pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
        <div className="text-xs text-white/40">© {new Date().getFullYear()} Tony Yoga. {t("mkt.rights")}</div>
        <div className="flex items-center gap-5 text-xs">
          <Link to="/home" className="text-white/60 hover:text-white transition">{t("mkt.student_signin")}</Link>
          <Link to="/login?admin=1" data-testid="footer-admin-signin" className="text-white/60 hover:text-[#B25A45] transition">{t("mkt.admin_signin")}</Link>
        </div>
      </div>
    </footer>
  );
}

function BestSellers() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/products/best-sellers?limit=8").then(({ data }) => setItems(data || [])).catch(() => setItems([])); }, []);
  if (!items.length) return null;
  return (
    <section className="px-5 py-14 sm:py-16" data-testid="home-best-sellers">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-end justify-between gap-3 mb-6">
          <div>
            <div className="eyebrow">The shop</div>
            <h2 className="serif text-3xl sm:text-4xl mt-1">Best sellers</h2>
          </div>
          <Link to="/shop" data-testid="home-best-sellers-all" className="text-sm font-semibold text-[#B25A45] hover:opacity-70 shrink-0">Shop all →</Link>
        </div>
        <div className="flex gap-4 overflow-x-auto no-scrollbar pb-2 snap-x">
          {items.map((p) => (
            <Link key={p.id} to={`/shop/${p.id}`} data-testid={`best-seller-${p.id}`} className="shrink-0 w-44 sm:w-52 snap-start group">
              <div className="relative aspect-square rounded-2xl overflow-hidden bg-[#F2F2EC]">
                {p.compare_at_price > p.price && (
                  <span className="absolute top-2 right-2 z-10 rounded-full bg-[#B25A45] px-2 py-0.5 text-[9px] uppercase tracking-widest font-bold text-white">Sale</span>
                )}
                {p.images?.[0]
                  ? <img src={p.images[0]} alt="" className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-500" />
                  : <div className="h-full w-full flex items-center justify-center"><Flower2 className="h-8 w-8 text-[#B25A45]/60" /></div>}
              </div>
              <div className="mt-2 text-[13px] font-semibold text-[#1C221F] leading-tight line-clamp-2">{p.title}</div>
              <div className="mt-0.5 flex items-baseline gap-1.5">
                <span className="text-sm text-[#B25A45] font-semibold">€{p.price}</span>
                {p.compare_at_price > p.price && <span className="text-xs text-[#9AA096] line-through">€{p.compare_at_price}</span>}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function BooksSection() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/products?category=books").then(({ data }) => setItems((data || []).slice(0, 4))).catch(() => setItems([])); }, []);
  if (!items.length) return null;
  return (
    <section className="relative overflow-hidden px-5 py-16 sm:py-24 bg-[#141815] text-[#FAFAF7]" data-testid="home-books">
      {/* warm glow */}
      <div className="pointer-events-none absolute -top-24 right-0 h-[420px] w-[420px] rounded-full bg-[#B25A45]/20 blur-[120px]" />
      <div className="pointer-events-none absolute bottom-0 left-1/4 h-[300px] w-[300px] rounded-full bg-[#839682]/10 blur-[120px]" />
      <div className="relative mx-auto max-w-5xl">
        <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-16">
          <div className="inline-flex items-center gap-2 eyebrow !text-[#E0A38F]"><BookOpen className="h-3.5 w-3.5" /> Written by Tony Sanchez</div>
          <h2 className="serif text-3xl sm:text-5xl mt-3 leading-[1.05]">Read the method</h2>
          <p className="text-[15px] sm:text-base text-[#B7BEB4] mt-4">
            Five decades on the mat, distilled into practice manuals used by students and teachers worldwide.
            Take the work off the screen and onto your shelf.
          </p>
        </div>

        <div className="grid gap-6 sm:gap-8 sm:grid-cols-2 max-w-3xl mx-auto">
          {items.map((p, i) => {
            const buy = p.external_amazon_link || `/shop/${p.id}`;
            return (
              <div key={p.id} data-testid={`home-book-${p.id}`} className="group relative rounded-3xl bg-white/[0.04] ring-1 ring-white/10 p-5 sm:p-6 backdrop-blur-sm transition-all duration-300 hover:bg-white/[0.07] hover:ring-white/20">
                <div className="flex gap-5">
                  <Link to={`/shop/${p.id}`} className="shrink-0" data-testid={`home-book-cover-${p.id}`}>
                    <div className="relative w-28 sm:w-32">
                      {/* shelf shadow */}
                      <div className="absolute -bottom-2 left-1/2 h-4 w-[85%] -translate-x-1/2 rounded-full bg-black/50 blur-md" />
                      <div className="relative aspect-[2/3] rounded-lg overflow-hidden shadow-2xl shadow-black/60 ring-1 ring-white/10 transition-transform duration-500 group-hover:-translate-y-1 group-hover:-rotate-1">
                        {p.type === "ebook" && (
                          <span className="absolute top-1.5 left-1.5 z-10 rounded-full bg-[#B25A45] px-2 py-0.5 text-[8px] uppercase tracking-widest font-bold text-white">eBook</span>
                        )}
                        {p.images?.[0]
                          ? <img src={p.images[0]} alt={p.title} className="h-full w-full object-cover" loading="lazy" />
                          : <div className="h-full w-full flex items-center justify-center bg-white/5"><BookOpen className="h-8 w-8 text-[#E0A38F]/60" /></div>}
                      </div>
                    </div>
                  </Link>

                  <div className="min-w-0 flex-1 flex flex-col">
                    <div className="flex items-center gap-1 text-[#E7B84B]">
                      {[0, 1, 2, 3, 4].map((s) => <Star key={s} className="h-3 w-3 fill-current" />)}
                      <span className="ml-1 text-[10px] text-[#8A928A]">Reader favourite</span>
                    </div>
                    <Link to={`/shop/${p.id}`} className="serif text-lg sm:text-xl leading-tight mt-1.5 hover:text-[#E0A38F] transition-colors">{p.title}</Link>
                    {p.author && <div className="text-[11px] text-[#8A928A] mt-0.5">by {p.author}</div>}
                    <p className="text-[12px] text-[#B7BEB4] mt-2 line-clamp-3 leading-relaxed">{p.description}</p>
                    <div className="mt-auto pt-4 flex items-center gap-3">
                      {p.price > 0 && <span className="serif text-xl text-[#FAFAF7]">€{p.price}</span>}
                      <a
                        href={buy} target={p.external_amazon_link ? "_blank" : undefined} rel="noopener noreferrer"
                        data-testid={`home-book-buy-${p.id}`}
                        className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-[#E0A38F] px-4 py-2 text-[12px] font-bold text-[#141815] hover:bg-white transition-colors"
                      >
                        {p.type === "ebook" ? "Get the eBook" : "Buy on Amazon"} <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[11px] text-[#8A928A]">
          <span className="inline-flex items-center gap-1.5"><Truck className="h-3.5 w-3.5 text-[#839682]" /> Ships worldwide via Amazon</span>
          <span className="inline-flex items-center gap-1.5"><BookOpen className="h-3.5 w-3.5 text-[#839682]" /> Kindle &amp; paperback editions</span>
          <Link to="/shop" data-testid="home-books-all" className="inline-flex items-center gap-1 font-semibold text-[#E0A38F] hover:text-white transition-colors">Browse the shop <ArrowRight className="h-3 w-3" /></Link>
        </div>
      </div>
    </section>
  );
}


function QuizBanner() {
  return (
    <section className="px-5 py-14 sm:py-20" data-testid="home-quiz-banner">
      <div className="mx-auto max-w-5xl rounded-[2rem] bg-[#1C221F] text-[#FAFAF7] px-6 sm:px-12 py-12 sm:py-16 relative overflow-hidden">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-[#B25A45]/20 blur-3xl" />
        <div className="absolute -left-10 -bottom-20 h-56 w-56 rounded-full bg-[#839682]/15 blur-3xl" />
        <div className="relative">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-[11px] uppercase tracking-widest font-bold text-[#E0A38F]">
            <Compass className="h-3.5 w-3.5" /> Not sure where to start?
          </div>
          <h2 className="serif text-4xl sm:text-5xl leading-[1.05] mt-4 max-w-2xl">
            Find your path in <span className="text-[#E0A38F]">60 seconds</span>.
          </h2>
          <p className="text-[15px] sm:text-lg text-[#B7BEB4] mt-4 max-w-xl leading-relaxed">
            Answer five quick questions and we'll match you with the right Core program and membership — built around your goals, level and schedule.
          </p>
          <Link
            to="/find-your-path"
            data-testid="home-quiz-banner-cta"
            className="pill mt-7 !bg-[#B25A45] !text-white hover:!bg-[#9c4c39] !py-3.5 !px-7 text-base"
          >
            Take the quiz <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}

function DiscoverStrip() {
  return (
    <section id="discover" className="mx-auto max-w-6xl px-4 sm:px-6 py-14 sm:py-20">
      <div className="rounded-3xl bg-[#1C221F] text-[#FAFAF7] p-8 sm:p-12 grid lg:grid-cols-[1.3fr,1fr] gap-8 items-center overflow-hidden relative">
        <div>
          <div className="eyebrow !text-[#B25A45] mb-3">Explore</div>
          <h2 className="serif text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">Find the right practice for today.</h2>
          <p className="text-white/70 leading-relaxed max-w-md text-sm sm:text-base mb-6">
            Filter the whole library by focus, level, style and the minutes you have — from a 5-minute reset to a full Core sequence.
          </p>
          <div className="flex flex-wrap gap-2 mb-7">
            {["Back care", "Flexibility", "Stress relief", "5-15 min", "Beginner"].map((x) => (
              <span key={x} className="text-xs rounded-full bg-white/10 px-3 py-1.5 text-white/80">{x}</span>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Link to="/discover" data-testid="home-discover-cta" className="pill pill-primary">
              <Compass className="h-4 w-4" /> Explore the library
            </Link>
            <Link to="/meditations" data-testid="home-meditations-cta" className="pill pill-ghost !bg-white/10 !text-white !border-white/20 hover:!bg-white/20">
              <Moon className="h-4 w-4" /> Meditation &amp; Breathwork
            </Link>
            <Link to="/find-your-path" data-testid="home-quiz-cta" className="pill pill-ghost !bg-white/10 !text-white !border-white/20 hover:!bg-white/20">
              <Compass className="h-4 w-4" /> Find your path
            </Link>
          </div>
        </div>
        <div className="hidden lg:grid grid-cols-2 gap-3">
          {["https://images.unsplash.com/photo-1506126279646-a697353d3166?w=400&q=80",
            "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80",
            "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=400&q=80",
            "https://images.unsplash.com/photo-1545205597-3d9d02c29597?w=400&q=80"].map((src, i) => (
            <div key={i} className={`rounded-2xl overflow-hidden aspect-square ${i % 2 ? "translate-y-4" : ""}`}>
              <img src={src} alt="" className="h-full w-full object-cover" loading="lazy" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const COMING_SOON = [
  { icon: User, title: "Private sessions", desc: "1:1 practice with Tony" },
  { icon: GraduationCap, title: "Teacher training", desc: "CE-eligible advanced study" },
  { icon: Flame, title: "Challenges", desc: "30-day practice streaks" },
];

function ComingSoon() {
  return (
    <section id="coming-soon" className="mx-auto max-w-6xl px-4 sm:px-6 pb-14 sm:pb-20">
      <div className="mb-6">
        <div className="eyebrow mb-2">On the way</div>
        <h2 className="serif text-2xl sm:text-3xl leading-tight">More practice, coming soon.</h2>
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl" data-testid="home-coming-soon">
        {COMING_SOON.map((c) => (
          <li key={c.title} className="rounded-2xl bg-[#F2F2EC] border border-[#E5E6DF] p-4 flex flex-col gap-2">
            <div className="h-9 w-9 rounded-full bg-white flex items-center justify-center text-[#B25A45] shrink-0">
              <c.icon className="h-4 w-4" />
            </div>
            <div className="text-sm font-semibold text-[#1C221F] leading-tight">{c.title}</div>
            <div className="text-[11px] text-[#6B7269] leading-snug flex-1">{c.desc}</div>
            <span className="text-[9px] uppercase tracking-widest font-bold text-[#B25A45]">Coming soon</span>
          </li>
        ))}
      </ul>
    </section>
  );
}


export default function Marketing() {
  const openApp = () => {
    // If already installed as PWA, go to home; else route into the app shell.
    window.location.href = isStandalone() ? "/home" : "/home";
  };
  useEffect(() => {
    document.title = "Tony Yoga — Slow down. Breathe in. Begin again.";
  }, []);
  return (
    <div data-testid="marketing-site" className="min-h-screen bg-[#FAFAF7]">
      <FreeClassRibbon />
      <Nav onOpenApp={openApp} />
      <Hero onOpenApp={openApp} />
      <FeatureStrip />
      <StatsBar />
      <Story />
      <ValueProps />
      <Programs />
      <QuizBanner />
      <BestSellers />
      <BooksSection />
      <DiscoverStrip />
      <ComingSoon />
      <Retreats />
      <HeroTestimonial />
      <Testimonials />
      <InlineSignup />
      <FAQ />
      <AppCTA onOpenApp={openApp} />
      <InstagramReels />
      <Footer />
      <AssistantWidget />
    </div>
  );
}
