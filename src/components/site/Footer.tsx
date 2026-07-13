import { HeartPulse, Github, Twitter, Linkedin } from "lucide-react";
import { Link } from "@tanstack/react-router";

export function Footer() {
  return (
    <footer id="contact" className="border-t border-border bg-muted/30">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-hero text-white">
              <HeartPulse className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold">MedTour</span>
          </div>
          <p className="text-sm text-muted-foreground">
            AI-powered healthcare navigation for travellers in India.
          </p>
          <div className="flex gap-3 pt-2 text-muted-foreground">
            <Twitter className="h-5 w-5 hover:text-foreground" />
            <Linkedin className="h-5 w-5 hover:text-foreground" />
            <Github className="h-5 w-5 hover:text-foreground" />
          </div>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">Product</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><a href="/#features">Features</a></li>
            <li><a href="/#how">How it works</a></li>
            <li><Link to="/dashboard">Dashboard</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">Company</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><a href="/#faq">FAQ</a></li>
            <li>About</li>
            <li>Careers</li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">Contact</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>support@medtour.example</li>
            <li>+91 800-000-0000</li>
            <li>New Delhi, India</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} MedTour. All rights reserved.
      </div>
    </footer>
  );
}
