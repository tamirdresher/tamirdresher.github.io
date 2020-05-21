---
layout: post
title: "Microsoft Build 2020 conference summary"
date: 2020-05-21
---
# Build 2020 summary (so far)

In the last two days Microsoft ran its developer conference. This year, for the first time it was completely virtual and free.

There were many announcements as you can read in their [announcement book](https://news.microsoft.com/build-2020-book-of-news/), but I picked some of them that I think are more interesting.

## Developer tools
	

1. [Visual Studio 2019 v16.6](https://devblogs.microsoft.com/visualstudio/visual-studio-2019-v16-6-and-v16-7-preview-1-ship-today/)
2. [.NET 5 preview 4](https://devblogs.microsoft.com/dotnet/announcing-net-5-preview-4-and-our-journey-to-one-net/) – the next generation of .NET Core and .NET Framework.
 Includes
   *  Perf improvements in HTTP (1.1 and 2) processing.
   *  New GC heap called Pinned Object Heap – this will improve perf in various scenarios that involve low level interaction (such as networking).
   *  Better support for Containers.
   *  Improved JSON API (and easier [migration form Json.NET](https://docs.microsoft.com/dotnet/standard/serialization/system-text-json-migrate-from-newtonsoft-how-to)).
   *  [C# Source Generators](https://devblogs.microsoft.com/dotnet/introducing-c-source-generators/) - a new C# compiler feature that lets C# developers inspect user code and generate new C# source files that can be added to a compilation.
3. [C# 9 preview (not final)](https://devblogs.microsoft.com/dotnet/welcome-to-c-9-0/) –
   * Exciting features and improvements in pattern-matching.
   * Init-only properties – marking a property so you could set its value during the object initialization.
   * Records – marking a class as &quot;data object&quot; so you can give a value-like behavior such as making it immutable with equality functionality and use the new With-Expression so you can clone it and define only the changes you want from the source object (e.g. `var otherPerson = person with { LastName = "Dresher" };`)
   * Top-level programs – now you would be able to create a new c# application without all the ceremony of the Program class and main method, basically just write the main method code in the main file.
   * Targeted-type new – essentially be able to create a new object without specifying its type for example: Point p = new (3, 5);
   * Covariant returns – be able to override a method and specify its return type to be different than the one in the base as long as the type derived from it
   ```csharp
    abstract class Animal
    {
          public abstract Food GetFood();
    }

    class Tiger : Animal
    {
          public override Meat GetFood() => ...;
    }
   ```  

4. [NET Multi-platform App UI](https://devblogs.microsoft.com/dotnet/introducing-net-multi-platform-app-ui/) - will allow developers to build apps for any device from a single codebase and project system, including desktop and mobile devices across operating systems.
  5. [ASP.NET Blazor now supports WebAssembly](https://devblogs.microsoft.com/aspnet/blazor-webassembly-3-2-0-now-available/) - ASP.NET Blazor, which allows developers to build interactive web UIs with C# instead of JavaScript, now supports WebAssembly. This added capability means developers can build client-side web apps that run completely in the browser with .NET.
  6. [Visual Studio Codespaces](https://devblogs.microsoft.com/visualstudio/expanding-visual-studio-2019-support-for-visual-studio-codespaces/) - enables developers to work remotely from anywhere with fully configured cloud-hosted development environments that can be created in minutes.
  7. [Fluid Framework](https://support.microsoft.com/en-us/office/get-started-with-fluid-framework-preview-d05278db-b82b-4d1f-8523-cf0c9c2fb2df) – an open-source client side libraries that expose distributed data structures ([DDS](https://www.usenix.org/legacy/publications/library/proceedings/osdi2000/full_papers/gribble/gribble_html/node2.html)) which essentially let you develop applications with instantaneous coauthoring, in-line mentions, and updateable components (think of google docs and alike).
  8. [ML.NET Model Builder is now a part of Visual Studio](https://devblogs.microsoft.com/dotnet/ml-net-model-builder-is-now-a-part-of-visual-studio/) - create custom machine learning models without having prior machine learning experience and without leaving the .NET ecosystem.
  9. [Windows Terminal](https://devblogs.microsoft.com/commandline/windows-terminal-1-0/) – new and advanced terminal that let you run multiple shells in a single place with Tabs, Panes and advanced customization options.
  10. [Windows Package Manager](https://devblogs.microsoft.com/commandline/windows-package-manager-preview/).


## Azure

1. [Azure ARC-enabled Kuberenests clusters (PUBLIC PREVIEW)](https://azure.microsoft.com/en-us/blog/azure-arc-enabled-kubernetes-preview-and-new-ecosystem-partners/) - This one is really interesting for organizations that still have workloads running on-prem (like we have in Clarizen). Azure ARC is set of technologies that allows a company to manage resources in hybrid mode (on its datacenetes, azure and even competing cloud like AWS and GCP).
 MS now added support for Kubernetes. With this, anyone can use Azure Arc to connect and configure any Kubernetes cluster across customer datacenters, edge locations, and multi-cloud.
 (side note: this is also interesting because of the partnership between Azure and Oracle cloud that can make the migration of the oracle database easier and with [low latency](https://docs.oracle.com/en/solutions/learn-azure-oci-interconnect/index.html#GUID-A3BCA684-47C4-4644-90E8-99A7E3E0A6FE)).
2. [Azure monitor telemetry tools maximize cloud and on-premises resources and apps](https://azure.microsoft.com/en-us/updates/.azure-monitor-enhancements-are-now-available/) – There are many interesting insights the Azure monitor can find of telemetry coming from servers and application, and this can (allegedly) works seamlessly with windows servers and application running on-prem.
3. [Azure cosmos db serverless addresses intermittent traffic and &quot;bursty&quot; workloads for small apps](https://devblogs.microsoft.com/cosmosdb/autoscale-serverless-offers/) – Azure Cosmos DB can now scales the RU/s (Request Unit per Sec == Throughput) based on usage and therefore the billing is set based on usage and not up front.
4. Cosmos DB enhanced key and data recovery options for enterprise and mission-critical apps – BYOK (bring your own key) feature and ability to recover data from a specific period and restore at any time with point-in-time backup and restore for Cosmos DB.
5. [Azure Synapse Link](https://azure.microsoft.com/en-us/blog/azure-analytics-clarity-in-an-instant/) – Azure Synapse was initially created to be the next generation DWH. Now it became the Azure offering for [Data Mesh](https://www.thoughtworks.com/radar/techniques/data-mesh) which supports Hybrid Transactional Analytical Processing (HTAP). In other words, you can link all datas ources to Synapse and automatically get [analytics](https://azure.microsoft.com/en-us/services/synapse-analytics/#overview) capabilities including out-of-the-box support for PowerBI and AutoML.

## Teams and the Power Platform

1. [Organizations can now schedule, hold virtual visits with bookings app in microsoft teams](https://aka.ms/Bookings_Virtual_Visits) – making it easy to create appointments between multiple people (even those who are external to the organization).
2. [Many customizations and developers extensibility options](https://www.microsoft.com/en-us/microsoft-365/blog/2020/05/19/microsoft-teams-fluid-framework-new-microsoft-365/). 