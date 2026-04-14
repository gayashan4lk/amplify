import prisma from "@/lib/prisma";

export default async function Home() {

  const posts = await prisma.post.findMany()

  return (
    <div>
      <main>
        <h1>Posts</h1>
        <ul>
          {posts.map(post => (
            <li key={post.id}><h1 className="text-2xl font-black">{post.title}</h1> {post.content}</li>
          ))}
        </ul>
      </main>
    </div>
  );
}
