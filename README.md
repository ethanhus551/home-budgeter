# Home Affordability Dashboard

**Find out what a house will really cost you, and how much house you can
actually afford.**

Most mortgage calculators show you one number: the loan payment. But your real
monthly cost also includes property tax, insurance, HOA fees, mortgage
insurance and upkeep. And the cash you need on closing day is a lot more than
the down payment.

This dashboard adds it all up. It also answers the questions you actually have
when you're house hunting:

- *How much house can I afford?*
- *This place is over budget. What would make it work?*
- *Should I buy points or put more money down?*
- *What happens if rates go up before I lock?*
- *Which of these three houses is the better deal?*

---

## Contents

1. [Getting started](#getting-started)
2. [Terms you'll see](#terms-youll-see)
3. [Step by step: using the dashboard](#step-by-step-using-the-dashboard)
4. [Answering common questions](#answering-common-questions)
5. [Where to find your numbers](#where-to-find-your-numbers)
6. [What the dashboard doesn't account for](#what-the-dashboard-doesnt-account-for)
7. [For developers](#for-developers)

---

## Getting started

You need Python 3.11 or newer on your computer. Open PowerShell in this folder
and run these once:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

Then, any time you want to use it:

```powershell
.venv\Scripts\streamlit run src\house_calc\app.py
```

It opens in your web browser (usually at `http://localhost:8501`; the terminal
shows the exact address). Everything runs on your own computer, and none of
your numbers are sent anywhere. To close it, press `Ctrl+C` in the terminal.

---

## Terms you'll see

| Term | What it means |
|---|---|
| **P&I** | Principal & interest: the mortgage payment itself. Principal pays down the loan; interest is the bank's fee for lending. |
| **Monthly total** | Everything you'll pay each month to own the home: P&I + property tax + insurance + HOA + PMI + upkeep. |
| **Cash to close** | All the money you need on closing day: down payment + closing costs + any points. |
| **Closing costs** | One-time fees for buying: lender fees, title insurance, appraisal, inspection, etc. Usually 2–5% of the price. |
| **PMI** | Private mortgage insurance. If you put down less than 20%, the lender charges this monthly to protect *itself*. It goes away once you've paid the loan down to 80% of the home's price. |
| **LTV** | Loan-to-value: your loan as a % of the home's price. 10% down = 90% LTV. |
| **Points** | An optional upfront fee to get a lower interest rate. One point usually costs 1% of the loan and cuts the rate by about 0.25%. |
| **Break-even** | How many months of lower payments it takes to earn back what you paid for points. |
| **DTI** | Debt-to-income ratio: your monthly debts (including the new house) ÷ your monthly income before tax. Lenders cap this, often at 36–45%. |
| **Equity** | The part of the home you actually own: your down payment plus the loan principal you've paid off. |

---

## Step by step: using the dashboard

The dashboard opens with an example filled in: a **$450,000 house, 10% down,
6.5% rate**, for someone earning **$12,500/month** with **$80,000** saved.
Follow along with those numbers first, then put in your own.

All your inputs are in the **sidebar on the left**. Change any number and
everything updates right away.

### 1. Tell it about yourself (sidebar → **Buyer**)

Do this first. These numbers are your limits, and everything else is measured
against them.

- **Cash available**: everything you can spend on buying: down payment,
  closing costs, points. **Don't include your emergency fund.**
- **Target monthly payment**: the most you're comfortable paying each month
  for *everything*, not just the mortgage. Be honest. This is about what fits
  your life, not what the bank will approve.
- **Gross monthly income**: before taxes. Combine incomes if you're buying
  with someone.
- **Other monthly debt**: car payments, student loans, minimum credit card
  payments. Don't include rent; that stops when you buy.
- **Max DTI**: your lender's limit. 36% is the cautious default; many lenders
  go up to 43–45%. Ask yours.
- **Years expected to stay**: your best guess. This matters more than you'd
  think. It decides whether points are worth buying and what owning really
  costs you.

### 2. Tell it about a house (sidebar → **Property**)

- **Price**: listing price or what you plan to offer.
- **Annual property tax**: usually on the listing. If not, look up the
  county's tax rate and multiply by the price.
- **Annual insurance**: get a real quote if you can.
- **Monthly HOA**: homeowners association fee; 0 if there isn't one.
- **Maintenance**: what you'll spend fixing and maintaining the house each
  year, as a % of its value. 1% is the usual rule of thumb. Use 2% or more for
  an older home.

### 3. Tell it about the loan (sidebar → **Loan** and **Closing costs**)

- **Down payment**: enter it as a **%** of the price or a **$** amount (switch
  with the buttons).
- **Base rate**: the interest rate you've been quoted *without* points.
- **Term**: 30 years is most common; 15-year loans have bigger payments but
  far less interest.
- **Points**, **Rate cut per point**, **Point cost**: leave points at 0 to
  start. Your lender's quote tells you the real trade.
- **PMI rate**: typically 0.3%–1.5% of the loan per year, depending on your
  credit score. Only matters if you're putting down less than 20%.
- **Closing costs**: copy these from a lender's Loan Estimate if you have one.
  Otherwise the defaults are reasonable placeholders. **Moving & repairs**
  isn't a loan cost, but it comes out of the same pot of cash, so include it.

### 4. Read the four cards at the top

These are your answer at a glance. With the example numbers:

| Card | Example | What it's telling you |
|---|---|---|
| **Monthly total** | **$3,704** (↑ $504 vs target) | The real monthly cost. Red means it's over your budget. |
| **Cash to close** | **$57,150** ($22,850 left over) | What you need on closing day. Green means you have enough, with this much spare. |
| **DTI** | **34.4%** (max 36%) | Under your lender's limit, but only just. |
| **Affordable price** | **$388,808** (limited by target payment) | The most expensive house that fits **all** your limits (budget, cash and DTI), plus which one runs out first. |

Yellow warning banners above the cards spell out any problem.

**What the example says:** you have the cash, and the bank would probably
approve this. But it's **$504 a month over what you said you're comfortable
with**, and your own budget puts you at about **$389,000**. So either look at
cheaper homes, or check the tabs below for ways to bring the payment down.

### 5. Explore the tabs

Below the cards are seven tabs, one for each question.

#### Monthly cost: *Where's my money going?*
A bar showing each piece of your monthly payment, with your target marked, plus
a table of the exact amounts. Look for surprises. PMI and maintenance often add
more than people expect.

Below that, **Cost of ownership** shows what owning costs over the years you
plan to stay:
- **Total paid**: every dollar you'll spend, apart from the down payment.
- **Principal paid down**: the part of that which becomes *your* equity, which
  you get back when you sell.
- **Net cost**: the money that's truly gone (interest, tax, insurance, PMI,
  upkeep, fees). **This is the number to weigh against what you'd pay in rent
  over the same years.**

#### Amortisation: *How fast does the loan shrink, and when does PMI stop?*
- The line shows how much you owe over time. It falls slowly at first,
  because early payments are mostly interest.
- The **pink line** marks the month PMI stops. The **dotted line** marks when
  you plan to move. If you move before PMI stops, you'll pay it the whole time
  you own the house.
- The bar chart shows, year by year, how much of your payment went to
  interest versus actually paying off the house.

#### Points: *Is buying points worth it?*
Enter a number of points to try. You'll see what they cost, how much they
save each month, and the **break-even**: how long until the savings repay the
cost.
- **"Before you move"** (green): points pay off; you come out ahead.
- **"After you move"** (red): you'd sell before earning the money back. Skip
  the points.

#### Rate sensitivity: *What if rates change before I lock in?*
Your monthly total at rates from 1% lower to 1% higher than your quote. Find
where the line crosses your target. That's how much rates can rise before this
house is out of budget.

#### Goal-seek: *What would make this house work?*
- **Maximum price by constraint**: the most you could pay under each of your
  three limits. The ✓ shows which one is holding you back.
- **Hit a monthly payment at this price**: type the monthly payment you want
  and it tells you how many **points** or how big a **down payment** would get
  you there. "Not reachable" means that route alone can't do it.

#### Points vs down: *I've got some spare cash. Points or a bigger down payment?*
Enter how much extra cash you could spend (it starts with what you'd have left
after closing). It compares:
- spending it on **points** (lower rate), versus
- adding it to your **down payment** (smaller loan, maybe no PMI),

over the years you plan to stay, and tells you which one costs less. Tip: if
the extra cash gets you to 20% down, the down payment usually wins, because
PMI disappears.

#### Compare: *Which option is best?*
Put up to three options side by side. See the next step.

### 6. Save options and compare them

1. Set up an option, for example *"Oak St, 10% down"*.
2. Go to the **Compare** tab, type a name, click **Save current**.
3. Change things (a different house, 20% down, a lender's quote with points)
   and save again. You can keep three; a fourth replaces the oldest.
4. The table puts your current inputs next to every saved option: monthly
   cost, cash needed, DTI, when PMI ends, net cost over your stay, and more.
5. Click **Load into inputs** to bring a saved option back and keep adjusting
   it, or **Remove** to delete it.

#### Save & share: *Keep my plan, or send it to someone*
See step 7.

### 7. Save and share your plan

Once you've worked out a plan, open the **Save & share** tab.

1. **Name it** (*"Oak St, 10% down, 1 point"*) and add **notes**: what you
   decided and why, questions for the lender, next steps.
2. Then share it in whichever way suits:
   - **Download summary** saves a nicely formatted one-page report: the
     verdict (over or under budget, enough cash, DTI OK), the key numbers,
     monthly and closing costs, the loan, cost of owning over your stay,
     what you can afford, what happens if rates change, any options you
     compared, your notes, and all your inputs. It opens in any web browser
     and can be **printed or saved as a PDF**. Email it to a partner, a
     parent, or your lender.
   - **Share a link**: anyone who opens it sees the dashboard with exactly
     your numbers, and can play with them without changing yours.
   - **Text summary**: a plain-text version with a copy button, for pasting
     into a text message or email.
3. **To pick up where you left off**, upload a summary you downloaded under
   **Open a saved plan**, or just open your link again.

Good to know:
- Your browser's address bar **always** holds a link to your current plan,
  so refreshing the page or bookmarking it keeps your numbers.
- The link and the summary include the options saved on the **Compare** tab
  too.
- The app doesn't store your plan anywhere; it lives only in the link and the file. Anyone
  you give the link or file to can see them, so share with care.
- Opening a link or summary replaces whatever is currently in the dashboard.

---

## Answering common questions

**"How much house can I afford?"**
Fill in the **Buyer** section, then read the **Affordable price** card. Check
which limit it names:
- *target payment*: your own budget is the limit. Raising your target or
  finding a lower rate helps most.
- *cash to close*: you need more savings, a smaller down payment %, or lower
  closing costs (try the "$ amount" setting under **Goal-seek** in the
  sidebar).
- *max DTI*: the bank's limit. Paying off other debt helps directly.

**"I love this house but it's over budget."**
Go to **Goal-seek** and enter your target payment. It tells you how much down
payment or how many points would get you there. Then check **Points vs down**
to see which is cheaper over your stay.

**"Should I put down 20%?"**
Save one option at your current down payment and one at 20%, then compare.
Look at the difference in monthly total, cash to close, and net cost. Also
check the **Amortisation** tab: if PMI would only last a couple of years
anyway, putting down 20% may not be worth draining your savings.

**"My lender offered me a lower rate for points. Good deal?"**
Enter the points and the rate cut they offered on the **Points** tab. If
break-even comes before you plan to move, it's likely worth it. If it's close,
remember that plans change, and people often move or refinance sooner than
they expect.

**"I got quotes from three lenders."**
Enter each lender's rate, points and fees as a separate saved option and look
at **Net cost over stay** in **Compare**. The lowest rate isn't always the
cheapest loan once fees and points are included.

**"What if rates go up?"**
Check **Rate sensitivity**. If a 0.5% rise would push you over budget,
consider locking your rate sooner.

---

## Where to find your numbers

| Input | Where to look |
|---|---|
| Property tax | Listing page; the county assessor's website |
| Insurance | Quotes from an insurance agent or online |
| HOA | Listing page or the seller's agent |
| Rate, points, PMI, lender fees | A lender's **Loan Estimate**, a standard 3-page form you get within 3 days of applying |
| Title, appraisal | Loan Estimate, Section B/C |
| Prepaid escrow | Loan Estimate, Section F/G ("Prepaids" / "Initial escrow") |
| Inspection | Local inspectors; usually $300–$600 |
| Max DTI | Ask your lender or look at their pre-approval letter |

---

## What the dashboard doesn't account for

It's a planning tool, not financial advice. Keep these in mind:

- **Only fixed-rate mortgages.** It doesn't model adjustable-rate (ARM) loans.
- **Costs don't rise over time.** Real property tax, insurance and HOA fees
  usually go up every year.
- **It ignores what the house might be worth later.** Home value growth and
  the cost of selling (often 6–8% of the price) aren't included. Net cost is
  great for comparing options against each other, but it isn't a full
  rent-vs-buy answer.
- **It ignores what your cash could earn instead.** Money in a down payment
  isn't earning investment returns.
- **No tax effects**, such as the mortgage interest deduction.
- **Its DTI is a bit stricter than a lender's.** It includes maintenance,
  which lenders don't count. Set maintenance to 0 to match a lender's number.
- **PMI is simplified.** It assumes PMI drops off automatically at 80% of the
  purchase price. Real lenders may require you to request it or get an
  appraisal, or wait until 78%. FHA loans work differently.
- **Prepaid escrow is counted as a cost**, even though it's really tax and
  insurance paid early, so cost of ownership slightly overstates things. Set
  it to 0 for a more exact figure.
- **It doesn't limit points.** It may suggest 4, 5 or more points, but most
  lenders cap them around 2–4.
- **The monthly total shows your first-month cost.** If you have PMI, your
  payment drops once it ends.

---

## For developers

The calculations are kept separate from the screens, so they can be tested and
reused:

- `src/house_calc/mortgage.py`: payment, amortisation, PMI and break-even maths
- `src/house_calc/models.py`: input models and calculated fields
- `src/house_calc/solve.py`: goal-seek (works backwards from targets)
- `src/house_calc/compare.py`: cost of ownership, points vs down, rate sensitivity
- `src/house_calc/settings.py`: the inputs, and packing a plan into a link or file
- `src/house_calc/report.py`: the downloadable HTML and text summaries
- `src/house_calc/app.py`: the Streamlit dashboard

Run the tests with `.venv\Scripts\pytest`. The original design spec is in
`Home Affordability Dashboard Spec for Claude Code.md`.
