require 'liquid'

module Jekyll
  module FileFilters
    # Find team photos after directory moves or image format changes.
    def team_image(file)
      return file unless file.is_a?(String)

      path = file.delete_prefix("/")
      return file unless path.match?(%r{\Aimages/team/(?:Alumni/)?[^/]+\z})

      source = File.expand_path(@context.registers[:site].source)
      return file if File.file?(File.join(source, path))

      filename = File.basename(path)
      stem = File.basename(filename, File.extname(filename))
      candidates = ["images/team/Alumni", "images/team"].flat_map do |directory|
        Dir.glob(File.join(source, directory, "*")).sort.select { |candidate| File.file?(candidate) }
      end

      resolved = candidates.find { |candidate| File.basename(candidate) == filename }
      resolved ||= candidates.find do |candidate|
        File.basename(candidate, File.extname(candidate)) == stem &&
          %w[.png .jpg .jpeg .webp .gif .svg .avif].include?(File.extname(candidate).downcase)
      end
      return file unless resolved

      resolved = resolved.delete_prefix("#{source}/")
      return file.start_with?("/") ? "/#{resolved}" : resolved
    end

    # check if file exists
    def file_exists(file)
      path = File.join(Dir.getwd, file)
      # pass back filename if exists
      return File.file?(path) ? file : nil
    end

    # read text contents of file
    def file_read(file)
      path = File.join(Dir.getwd, file)
      return File.file?(path) ? File.read(path) : nil
    end
  end
end

Liquid::Template.register_filter(Jekyll::FileFilters)
