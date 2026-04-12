import { useEffect, useRef } from 'react';
import Head from 'next/head';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/dist/ScrollTrigger';

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger);
}

export default function LandingPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const heroTitleRef = useRef<HTMLHeadingElement>(null);
  const subtitleRef = useRef<HTMLParagraphElement>(null);
  const metaRef = useRef<HTMLDivElement>(null);
  const heroCtaRef = useRef<HTMLAnchorElement>(null);
  const howSectionRef = useRef<HTMLElement>(null);
  const attackColRef = useRef<HTMLDivElement>(null);
  const defenseColRef = useRef<HTMLDivElement>(null);
  const howExplainerRef = useRef<HTMLParagraphElement>(null);
  const deliverableSectionRef = useRef<HTMLElement>(null);
  const statsSectionRef = useRef<HTMLElement>(null);
  const ctaSectionRef = useRef<HTMLElement>(null);
  const counter1Ref = useRef<HTMLSpanElement>(null);
  const counter2Ref = useRef<HTMLSpanElement>(null);
  const counter3Ref = useRef<HTMLSpanElement>(null);

  /* ── Three.js particle field ── */
  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      1,
      1000,
    );
    camera.position.z = 300;

    const COUNT = 800;
    const positions = new Float32Array(COUNT * 3);
    const velocities: { x: number; y: number; z: number }[] = [];
    const SX = 500, SY = 500, SZ = 300;

    for (let i = 0; i < COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * SX;
      positions[i * 3 + 1] = (Math.random() - 0.5) * SY;
      positions[i * 3 + 2] = (Math.random() - 0.5) * SZ;
      velocities.push({
        x: (Math.random() - 0.5) * 0.08,
        y: (Math.random() - 0.5) * 0.06,
        z: (Math.random() - 0.5) * 0.03,
      });
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 1.2,
      transparent: true,
      opacity: 0.35,
      sizeAttenuation: true,
      depthWrite: false,
    });

    scene.add(new THREE.Points(geometry, material));

    const hx = SX / 2, hy = SY / 2, hz = SZ / 2;
    let frameId: number;

    const tick = () => {
      frameId = requestAnimationFrame(tick);
      const p = geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < COUNT; i++) {
        const ix = i * 3;
        p[ix] += velocities[i].x;
        p[ix + 1] += velocities[i].y;
        p[ix + 2] += velocities[i].z;
        if (p[ix] > hx) p[ix] = -hx;
        else if (p[ix] < -hx) p[ix] = hx;
        if (p[ix + 1] > hy) p[ix + 1] = -hy;
        else if (p[ix + 1] < -hy) p[ix + 1] = hy;
        if (p[ix + 2] > hz) p[ix + 2] = -hz;
        else if (p[ix + 2] < -hz) p[ix + 2] = hz;
      }
      geometry.attributes.position.needsUpdate = true;
      renderer.render(scene, camera);
    };
    tick();

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, []);

  /* ── GSAP animations ── */
  useEffect(() => {
    /* Hero load sequence */
    const words = heroTitleRef.current?.querySelectorAll('.word');
    if (words?.length) {
      gsap.fromTo(
        words,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.15, ease: 'power2.out' },
      );
    }

    const titleDone = (words?.length || 1) * 0.15 + 0.3;

    if (subtitleRef.current) {
      gsap.fromTo(
        subtitleRef.current,
        { opacity: 0, y: 15 },
        { opacity: 1, y: 0, duration: 0.6, delay: titleDone, ease: 'power2.out' },
      );
    }
    if (metaRef.current) {
      gsap.fromTo(
        metaRef.current,
        { opacity: 0 },
        { opacity: 1, duration: 0.6, delay: titleDone + 0.4, ease: 'power2.out' },
      );
    }
    if (heroCtaRef.current) {
      gsap.fromTo(
        heroCtaRef.current,
        { opacity: 0 },
        { opacity: 1, duration: 0.6, delay: titleDone + 0.8, ease: 'power2.out' },
      );
    }

    /* Scroll sections */
    const howLabel = howSectionRef.current?.querySelector('.section-label');
    if (howLabel) {
      gsap.from(howLabel, {
        opacity: 0, y: 30, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: howLabel as Element, start: 'top 85%' },
      });
    }

    if (attackColRef.current) {
      gsap.from(attackColRef.current, {
        opacity: 0, x: -40, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: howSectionRef.current!, start: 'top 75%' },
      });
    }
    if (defenseColRef.current) {
      gsap.from(defenseColRef.current, {
        opacity: 0, x: 40, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: howSectionRef.current!, start: 'top 75%' },
      });
    }
    if (howExplainerRef.current) {
      gsap.from(howExplainerRef.current, {
        opacity: 0, y: 30, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: howExplainerRef.current, start: 'top 85%' },
      });
    }

    /* Deliverable cards */
    const cards = deliverableSectionRef.current?.querySelectorAll('.vuln-card');
    if (cards?.length) {
      gsap.from(cards, {
        opacity: 0, y: 30, duration: 0.6, stagger: 0.15, ease: 'power2.out',
        scrollTrigger: { trigger: deliverableSectionRef.current!, start: 'top 85%' },
      });
    }

    /* Stats section */
    if (statsSectionRef.current) {
      gsap.from(statsSectionRef.current, {
        opacity: 0, y: 30, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: statsSectionRef.current, start: 'top 85%' },
      });
    }

    /* Counter tweens */
    const counters = [
      { ref: counter1Ref, target: 1227, fmt: (v: number) => v.toLocaleString() },
      { ref: counter2Ref, target: 79, fmt: (v: number) => v + '%' },
      { ref: counter3Ref, target: 5, fmt: (v: number) => String(v) },
    ];
    counters.forEach(({ ref, target, fmt }) => {
      if (!ref.current) return;
      const obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.5,
        ease: 'power2.out',
        scrollTrigger: { trigger: ref.current, start: 'top 85%' },
        onUpdate() {
          if (ref.current) ref.current.textContent = fmt(Math.floor(obj.val));
        },
      });
    });

    /* CTA section */
    if (ctaSectionRef.current) {
      gsap.from(ctaSectionRef.current, {
        opacity: 0, y: 30, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: ctaSectionRef.current, start: 'top 85%' },
      });
    }

    /* Refresh ScrollTrigger after full page layout settles */
    const onLoad = () => ScrollTrigger.refresh();
    window.addEventListener('load', onLoad);

    /* Fallback: snap invisible animated elements to visible after 3s */
    const fallbackTimer = setTimeout(() => {
      document.querySelectorAll('.gsap-reveal').forEach((el) => {
        gsap.killTweensOf(el);
        gsap.set(el, { opacity: 1, x: 0, y: 0 });
      });
    }, 3000);

    return () => {
      ScrollTrigger.getAll().forEach((t) => t.kill());
      window.removeEventListener('load', onLoad);
      clearTimeout(fallbackTimer);
    };
  }, []);

  return (
    <>
      <Head>
        <title>CROSSEXAMINE</title>
        <meta
          name="description"
          content="Two AI agents. Your case documents. Every contradiction, ranked."
        />
        <style>{`
          .hero-word, .hero-fade { opacity: 0; }
          .cta-link {
            color: #e84040;
            text-decoration: none;
            font-size: 14px;
            font-family: 'IBM Plex Mono', monospace;
            transition: color 0.15s ease;
          }
          .cta-link:hover {
            color: #e8e8e8;
            text-decoration: underline;
          }
          .legal-texture {
            background:
              repeating-linear-gradient(
                to bottom,
                rgba(255,255,255,0.02) 0px,
                rgba(255,255,255,0.02) 1px,
                transparent 1px,
                transparent 5px
              ),
              url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E"),
              #0a0a0f;
          }
          ::selection {
            background: rgba(232, 64, 64, 0.3);
            color: #e8e8e8;
          }
        `}</style>
      </Head>

      <noscript>
        <style>{`.hero-word, .hero-fade { opacity: 1 !important; transform: none !important; }`}</style>
      </noscript>

      {/* WebGL canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          zIndex: -1,
          pointerEvents: 'none',
        }}
      />

      <main className="font-mono relative">
        {/* ═══ Section 1: Hero ═══ */}
        <section
          className="min-h-screen flex flex-col text-left"
          style={{ paddingLeft: '10vw' }}
        >
          <div className="flex-1 flex flex-col justify-center">
            <h1
              ref={heroTitleRef}
              className="text-[80px] leading-none font-semibold tracking-wider text-text-primary mb-8"
            >
              <span className="word hero-word inline-block">CROSS</span>
              <span className="word hero-word inline-block">EXAMINE</span>
            </h1>

            <p
              ref={subtitleRef}
              className="hero-fade text-reading text-[#999] max-w-[600px] mb-6"
            >
              Two AI agents. Your case documents. Every contradiction, ranked.
            </p>

            <div
              ref={metaRef}
              className="hero-fade text-label uppercase tracking-widest text-text-ghost"
            >
              BUILT AT LLM X LAW &mdash; STANFORD CODEX
              &nbsp;&nbsp;&#9679;&nbsp;&nbsp;HACKATHON 2026
            </div>
          </div>

          <div className="pb-16">
            <a
              ref={heroCtaRef}
              href="/upload"
              className="hero-fade cta-link"
            >
              BEGIN CROSS-EXAMINATION &rarr;
            </a>
          </div>
        </section>

        {/* ═══ Section 2: How It Works ═══ */}
        <section ref={howSectionRef} className="px-12 lg:px-24 py-24">
          <div className="section-label gsap-reveal text-label uppercase tracking-widest text-text-muted mb-12">
            HOW IT WORKS
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 mb-12">
            {/* Attack column */}
            <div ref={attackColRef} className="gsap-reveal pl-4 border-l-2 border-l-attack">
              <div className="flex justify-between items-center mb-3">
                <div className="text-label uppercase tracking-widest text-attack flex items-center gap-2">
                  <span className="inline-block w-1.5 h-1.5 bg-text-ghost" />
                  ATTACK &mdash; ROUND 1
                </div>
              </div>
              <div className="text-reading text-[#ccc]">
                <span className="float-right text-label text-text-ghost ml-4 mt-0.5">
                  [Case #2024-0472, pp. 4&ndash;5]
                </span>
                The witness claims she was at the intersection &quot;for a
                while&quot; before the collision. Traffic camera footage from
                Camera #5M-North (timestamp 20:22:14) shows the witness
                entering the frame for the first time at 8:22 PM. Prior
                footage from 19:45 to 20:05 shows no pedestrian matching the
                witness description in the intersection.
                <br /><br />
                The witness was not present during the period she implies. Her
                account of events leading up to the collision cannot be based
                on direct observation.
              </div>
            </div>

            {/* Defense column */}
            <div ref={defenseColRef} className="gsap-reveal pl-4 border-l-2 border-l-defense">
              <div className="flex justify-between items-center mb-3">
                <div className="text-label uppercase tracking-widest text-defense flex items-center gap-2">
                  <span className="inline-block w-1.5 h-1.5 bg-text-ghost" />
                  DEFENSE &mdash; ROUND 1
                </div>
              </div>
              <div className="text-reading text-[#ccc]">
                <span className="float-right text-label text-text-ghost ml-4 mt-0.5">
                  [Maintenance Report, App. C]
                </span>
                The characterization of being present &quot;for a while&quot;
                is subjective and does not constitute a precise time claim.
                Camera #5M-North covers only the north-facing angle and has
                documented blind spots along the eastern sidewalk per the
                Maintenance Report, Appendix C.
                <br /><br />
                The witness may have been present in an unmonitored area
                before entering frame at 20:22. The absence of footage is not
                evidence of absence.
              </div>
            </div>
          </div>

          <p
            ref={howExplainerRef}
            className="gsap-reveal text-body text-[#666] max-w-[700px]"
          >
            Each agent retrieves only what the documents actually say.
            No invented citations. No confident nonsense.
          </p>
        </section>

        {/* ═══ Section 3: The Deliverable ═══ */}
        <section ref={deliverableSectionRef} className="px-12 lg:px-24 py-24">
          <div className="section-label text-label uppercase tracking-widest text-text-muted mb-12">
            THE DELIVERABLE
          </div>

          {/* Card 1: HIGH */}
          <div className="vuln-card gsap-reveal mb-10 pl-4 border-l-2 border-l-attack">
            <div className="flex justify-between items-center mb-4">
              <span className="text-label uppercase tracking-widest font-semibold text-attack">
                HIGH
              </span>
            </div>
            <VulnField
              label="CLAIM"
              value='Witness stated she was present at the intersection "for a while" before the collision occurred'
            />
            <VulnField
              label="CONTRADICTION"
              value="Traffic camera #5M-North shows witness first entering frame at 20:22:14. No matching pedestrian visible in footage from 19:45-20:05."
            />
            <VulnField
              label="SOURCE"
              value="Police Incident Report Case #2024-0472, Camera Log pp. 4-5"
            />
            <VulnField
              label="WHY IT MATTERS"
              value="Undermines witness credibility on presence timeline. If not present before the collision, account of preceding events cannot be based on direct observation."
            />
          </div>

          {/* Card 2: MEDIUM */}
          <div className="vuln-card gsap-reveal mb-10 pl-4 border-l-2 border-l-amber">
            <div className="flex justify-between items-center mb-4">
              <span className="text-label uppercase tracking-widest font-semibold text-amber">
                MEDIUM
              </span>
            </div>
            <VulnField
              label="CLAIM"
              value='Witness described the vehicle as "speeding through the intersection"'
            />
            <VulnField
              label="CONTRADICTION"
              value="Skid marks measured 12 feet, consistent with 15-20 mph per accident reconstruction. Signal inoperative (flashing yellow) due to power outage."
            />
            <VulnField
              label="SOURCE"
              value="Accident Reconstruction Report p. 7, Signal Maintenance Log 2024-03-15"
            />
            <VulnField
              label="WHY IT MATTERS"
              value="Physical evidence contradicts characterization of excessive speed. 15-20 mph at an uncontrolled intersection is within reasonable operating speed."
            />
          </div>

          {/* Card 3: MEDIUM, CONCEDED */}
          <div className="vuln-card gsap-reveal mb-10 pl-4 border-l-2 border-l-amber">
            <div className="flex justify-between items-center mb-4">
              <span className="text-label uppercase tracking-widest font-semibold text-amber">
                MEDIUM
              </span>
              <span className="text-label uppercase tracking-wider text-amber">
                CONCEDED BY DEFENSE
              </span>
            </div>
            <VulnField
              label="CLAIM"
              value={'Witness stated she "clearly saw the driver\'s face" at the moment of collision'}
            />
            <VulnField
              label="CONTRADICTION"
              value="Power outage from 18:15-21:30 disabled all streetlights. Collision at 19:52, sunset at approximately 19:28 on March 15."
            />
            <VulnField
              label="SOURCE"
              value="Power Company Outage Report #PO-2024-0315, National Weather Service sunset data"
            />
            <VulnField
              label="WHY IT MATTERS"
              value="Post-sunset with no artificial lighting severely limits visibility. Positive facial identification under these conditions requires closer scrutiny."
            />
          </div>
        </section>

        {/* ═══ Section 4: Stats ═══ */}
        <section ref={statsSectionRef} className="gsap-reveal legal-texture px-12 lg:px-24 py-24">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-16 mb-12">
            <div>
              <span
                ref={counter1Ref}
                className="block text-[48px] font-semibold text-attack leading-none mb-4"
              >
                0
              </span>
              <div className="text-label uppercase tracking-widest text-[#888888] leading-relaxed">
                AI hallucination<br />
                cases in courts<br />
                globally
              </div>
            </div>
            <div>
              <span
                ref={counter2Ref}
                className="block text-[48px] font-semibold text-defense leading-none mb-4"
              >
                0%
              </span>
              <div className="text-label uppercase tracking-widest text-[#888888] leading-relaxed">
                of lawyers now<br />
                use AI tools
              </div>
            </div>
            <div>
              <span
                ref={counter3Ref}
                className="block text-[48px] font-semibold text-amber leading-none mb-4"
              >
                0
              </span>
              <div className="text-label uppercase tracking-widest text-[#888888] leading-relaxed">
                contradictions<br />
                surfaced in<br />
                Webb v. State
              </div>
            </div>
          </div>

          <p className="text-body text-[#666] max-w-[700px] mb-4">
            The hallucination problem is documented. CrossExamine builds the
            verification layer the industry is missing.
          </p>

          <p className="text-[10px] text-[#444] leading-relaxed">
            Sources: Charlotin AI Hallucination Database 2026, ABA TechReport
            2025, CrossExamine session 6EAAF93B
          </p>
        </section>

        {/* ═══ Section 5: CTA ═══ */}
        <section
          ref={ctaSectionRef}
          className="gsap-reveal px-12 lg:px-24 py-32 flex flex-col justify-center"
        >
          <div className="text-[36px] font-semibold tracking-wider text-text-primary mb-4">
            UPLOAD YOUR CASE
          </div>
          <p className="text-body text-text-muted mb-6">
            Documents are indexed locally. Nothing is stored.
          </p>
          <a href="/upload" className="cta-link">
            BEGIN &rarr;
          </a>
        </section>
      </main>
    </>
  );
}

function VulnField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2.5">
      <div className="text-label uppercase tracking-widest text-text-muted mb-1">
        {label}
      </div>
      <div className="text-body text-[#bbb]">{value}</div>
    </div>
  );
}
