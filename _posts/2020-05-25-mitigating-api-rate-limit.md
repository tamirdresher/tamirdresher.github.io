---
layout: post
title: "Mitigating the API Rate-Limit"
date: 2020-05-25
---

A few months ago we announced the beginning of rate-limiting in the Clarizen One API (read more here https://success.clarizen.com/hc/en-us/articles/360012223839-API-Updates-for-Developers). This created some reaction by our customers, and some requested guidance on how to change their custom applications to handle the new policy.

## What is the API rate-limit and why did Clarizen add it?
Clarizen API is used extensively by our customers; many of them built custom applications and custom integrations that use Clarizen’s advanced API [query language](https://api.clarizen.com/V2.0/services/data/Query) and backend calculations to implement complex scenarios to automate their business workflows.
![An avarage week of API usage in one datacenter]({{ site.url }}/assets/mitigating-api-rate-limit/typical-week-api-usage.png)*An avarage week of API usage in one datacenter*

Our API is scalable and performs well, but even with the best hardware and software, without setting limits, customers can create a load that will affect the performance and user experience of their tenant and sometimes even on other tenants
These are the types of issues you may see on the backend with such loads:
1.	Exhausted thread-pools
2.	Creating bottlenecks in DB connection pools
3.	Increasing the risk for locks and even deadlocks in the DB or other types of resources


Over time we discovered that some clients can create heavy loads on the API. At some point we even saw thousands of calls per second coming from a single client!
![Max API calls per sec from a single client in an average week]({{ site.url }}/assets/mitigating-api-rate-limit/max-request-count-per-sec-in-week.png)*Max API calls per sec from a single client in an average week*

So one good way to fix these issues is to avoid them in the first place, hence rate-limits were introduced.

## How the rate-limit works?
Clarizen looks at users from two angles, as an individual doing operations in the applications, and as a member of a tenant (organization) performing operation on behalf of the organization they belong to.
Most of the cases that involve API usage coming from the organization level of the operation - for example, syncing the currency rates from a financial system with Clarizen.
So simply put, the way our rate-limit works is that we count the amount of API calls made in a sliding window of 1 second from any user of your organization. This however has some exclusions:
1.	Any API call coming from the UI
2.	Any API call coming from Clarizen internal tools and integration platform

### What happens when my API call reaches the limit
If your API client triggers more requests than allowed in a single second, you will get a response with an HTTP status code 429 (too many requests).

Here is an example of a response:
```
HTTP/1.1 429 Too Many Requests
Cache-Control: no-cache, no-store
Pragma: no-cache
Content-Type: application/json; charset=utf-8
Expires: -1
Retry-After: 1
Content-Length: 121
Date: Mon, 25 May 2020 07:52:16 GMT
Connection: keep-alive

{"statusCode":"Too Many Requests","message":"API calls quota exceeded! maximum admitted 25 per Second.","retryAfter":"1"}
```

What you should understand from this is that the API client code you write should now be aware of such restrictions and should protect itself.

## How to avoid _429 Too Many Requests_
The first thing you need to understand is that there is no magic here, you have to design your API clients so that they will flood the API. This is generally true to any API you consume, and specifically the Clarizen API.

One of the most popular techniques to remedy the rate-limit response is by adding some kind of retry mechanism with backoffs (delays) between the attempts. The delay can be fixed so the same amount of time is waited for every time, or it can be with some randomization (known as [exponantial backoff](https://en.wikipedia.org/wiki/Exponential_backoff))

The following example show a C# program that calls the Clarizen API and simply runs in a loop until the call succeeds with some delay between each iteration. If the maximum amount of retries is reached, we just throw an exception (remember, there is no silver bullet).

{% gist 715974dcb32ba320d56349e077d037dc %}

Another option is to use a library that does a return logic for you. In the .NET ecosystem, [Polly](https://github.com/App-vNext/Polly) is a very powerful and popular option:

{% gist e1914eea15e9124d3c7d8d6bab98fe41 %}

Last, it's worth mentioning the popular [Ekin.Clarizen](https://github.com/ekincaglar/clarizen) library that provides a .NET Wrapper for Clarizen API v2.0. If you are using _Ekin.Clarizen_ then you would use

{% gist bea59955472f6886630d2b7ee9fa2479 %}

## Final words
API rate-limiting is a widely used and standard way to protect APIs from being flooded. I understand that it makes the client code more complex, and that it requires more work to protect your code from the new reality. At the same time, I’m sure and hope that you now understand that in the end this was introduced to give the best user experience possible for Clarizen users. With a simple change to your code and a bit of planning, you can easily tweak your code to make sure you won’t see any failures in your applications.